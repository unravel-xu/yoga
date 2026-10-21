"""Light Interaction: local macOS app with a responsive capture worker."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from pathlib import Path

import cv2
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings, QUrl
from PySide6.QtGui import QImage, QKeySequence, QShortcut, QDesktopServices
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox, QSlider, QFrame)

from interactive_app.canvas import InteractionCanvas
from interactive_app.platform_support import capture_backend, camera_settings_urls
from interactive_app.engine import (Tracker, LABELS, camera_devices,
                                    camera_permission, camera_permission_status, demo_state)

LOG = logging.getLogger(__name__)


class CameraWorker(QThread):
    message = Signal(str)
    failure = Signal(str)

    def __init__(self, index, options, parent=None):
        super().__init__(parent)
        self.index = index
        self.options = options
        self.packet = None
        self.lock = threading.Lock()
        self.calibration_requested = threading.Event()

    def take_packet(self):
        with self.lock:
            packet, self.packet = self.packet, None
        return packet

    def run(self):
        cap = None
        tracker = None
        try:
            self.message.emit("正在加载离线识别模型…")
            tracker = Tracker()
            if self.isInterruptionRequested():
                return
            self.message.emit("正在连接摄像头…")
            cap = cv2.VideoCapture(self.index, capture_backend())
            if not cap.isOpened():
                raise RuntimeError("摄像头无法打开。请点击“打开摄像头设置”检查权限和“允许桌面应用访问摄像头”，或关闭占用相机的软件并刷新设备。")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
            cap.set(cv2.CAP_PROP_FPS, 30)
            self.message.emit("已连接 · 面部与双手同时识别")
            last = time.monotonic()
            failed_reads = 0
            fps = 0.0
            while not self.isInterruptionRequested():
                ok, frame = cap.read()
                if not ok:
                    failed_reads += 1
                    if failed_reads >= 20:
                        raise RuntimeError("摄像头连接中断。重新插入设备，然后再次开始。")
                    self.msleep(50)
                    continue
                failed_reads = 0
                if self.options.get("mirror", True):
                    frame = cv2.flip(frame, 1)
                width = 640
                rgb = cv2.cvtColor(cv2.resize(frame, (width, round(frame.shape[0]*width/frame.shape[1]))), cv2.COLOR_BGR2RGB)
                if self.calibration_requested.is_set():
                    tracker.calibrate()
                    self.calibration_requested.clear()
                was_calibrating = bool(tracker.calibrating_until)
                state = tracker.process(rgb, self.options.get("sensitivity", 1.0))
                if was_calibrating and not tracker.calibrating_until:
                    self.message.emit("校准完成。试着微笑、张嘴或皱眉。" if tracker.calibration_samples else "校准未检测到面部，请看向镜头后重试。")
                now = time.monotonic()
                fps = .85*fps + .15/max(.001,now-last)
                state.fps = fps
                last = now
                image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()
                # A single-slot mailbox avoids a growing image queue if the UI
                # is briefly busy resizing or changing screens.
                with self.lock:
                    self.packet = (image, state)
                self.msleep(1)
        except Exception as error:
            LOG.exception("Camera/inference worker failed")
            self.failure.emit(str(error))
        finally:
            if cap is not None:
                cap.release()
            if tracker is not None:
                tracker.close()


STYLE = """
QMainWindow, QWidget { background: #0c111c; color: #dbe6f5; font-family: 'Noto Sans CJK SC', 'Segoe UI', 'Helvetica Neue', sans-serif; font-size: 13px; }
QWidget#sidebar { background: #121a28; border-right: 1px solid #253044; }
QLabel#eyebrow { color: #6e92bf; font-size: 10px; letter-spacing: 2px; }
QLabel#title { color: #f1f6ff; font-size: 25px; font-weight: 600; }
QLabel#subtitle, QLabel#hint { color: #8597b0; font-size: 12px; }
QLabel#section { color: #b5c8e1; font-size: 12px; font-weight: 600; }
QLabel#status { color: #8daccb; }
QLabel#emotion { color: #9ce9ec; font-size: 23px; font-weight: 500; }
QLabel#badge { background: #1a2639; color: #97b2d1; padding: 6px 10px; border-radius: 7px; }
QLabel { background: transparent; }
QSlider { background: transparent; }
QPushButton { background: #202e44; border: 1px solid #30445e; border-radius: 8px; padding: 10px 12px; color: #d5e4f9; }
QPushButton:hover { background: #2a3c57; }
QPushButton:disabled { color: #576981; border-color: #243247; }
QPushButton#primary { background: #7ce3df; border: none; color: #102932; font-weight: 600; }
QPushButton#primary:hover { background: #a0f4ef; }
QComboBox { background: #1a273a; border: 1px solid #2b3e58; border-radius: 7px; padding: 9px; }
QComboBox QAbstractItemView { background: #1a273a; selection-background-color: #334966; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #456078; border-radius: 4px; background: #162236; }
QCheckBox::indicator:checked { background: #7ce3df; border-color: #7ce3df; }
QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: #2a3a53; }
QSlider::sub-page:horizontal { background: #79d9d8; border-radius: 2px; }
QSlider::handle:horizontal { background: #d2ffff; width: 12px; margin: -4px 0; border-radius: 6px; }
QFrame#divider { color: #27364b; }
"""


class Window(QMainWindow):
    permissionResult = Signal(bool)

    def __init__(self, auto_request_permission=True, canvas_factory=InteractionCanvas,
                 settings_name="LightInteraction", display_name="光感互动 / Light Interaction"):
        super().__init__()
        self.display_name = display_name
        self.setWindowTitle("光感互动 · Light Interaction")
        self.resize(1320, 810)
        self.setMinimumSize(960, 620)
        self.setStyleSheet(STYLE)
        self.settings = QSettings("LightInteraction", settings_name)
        self.worker = None
        self.permission_pending = False
        self.capture_after_permission = False
        self.permission_status = "unknown"
        self.closing = False
        self.demo = False
        self.start_time = time.monotonic()
        self.worker_error = None
        self.options = {"mirror": self.settings.value("mirror", True, type=bool), "sensitivity": self.settings.value("sensitivity", 100, type=int)/100}
        self.devices = []
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.setCentralWidget(root)
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(288)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(24,24,24,20)
        side.setSpacing(9)
        layout.addWidget(self.sidebar)
        self.label(side, "LIGHT INTERACTION", "eyebrow")
        self.label(side, "光感互动", "title")
        self.label(side, "表情改变氛围 · 双手描绘光", "subtitle")
        self.divider(side)
        self.label(side,"摄像头", "section")
        self.camera = QComboBox()
        side.addWidget(self.camera)
        self.refresh = QPushButton("刷新设备")
        self.refresh.clicked.connect(self.refresh_devices)
        side.addWidget(self.refresh)
        self.start_button = QPushButton("开始互动")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.toggle_capture)
        side.addWidget(self.start_button)
        self.demo_button = QPushButton("体验演示")
        self.demo_button.clicked.connect(self.toggle_demo)
        side.addWidget(self.demo_button)
        self.divider(side)
        self.label(side,"画面与识别", "section")
        self.mirror = QCheckBox("镜像画面")
        self.mirror.setChecked(self.options["mirror"])
        self.mirror.toggled.connect(self.set_mirror)
        side.addWidget(self.mirror)
        self.video = QCheckBox("显示摄像头背景")
        self.video.setChecked(self.settings.value("video",True,type=bool))
        side.addWidget(self.video)
        self.debug_box = QCheckBox("显示手部骨架")
        side.addWidget(self.debug_box)
        self.sensitivity = self.slider(side,"表情灵敏度",60,180,round(self.options["sensitivity"]*100))
        self.strength = self.slider(side,"光效强度",30,150,self.settings.value("intensity",100,type=int))
        self.calibrate_button = QPushButton("校准中性表情")
        self.calibrate_button.setEnabled(False)
        self.calibrate_button.clicked.connect(self.calibrate)
        side.addWidget(self.calibrate_button)
        side.addStretch()
        self.fullscreen_button = QPushButton("全屏展示   " + ("⌘F" if sys.platform == "darwin" else "Ctrl+F"))
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        side.addWidget(self.fullscreen_button)
        hint = self.label(side,"捏合爆发 · 张掌扩环 · 挥手拖尾\nEsc 退出全屏 · 空格开始/暂停", "hint")
        hint.setWordWrap(True)
        panel = QWidget()
        right = QVBoxLayout(panel)
        right.setContentsMargins(20,20,20,16)
        right.setSpacing(12)
        header = QHBoxLayout()
        self.emotion = QLabel("等待互动")
        self.emotion.setObjectName("emotion")
        header.addWidget(self.emotion)
        header.addStretch()
        self.face_badge = QLabel("面部 —")
        self.hand_badge = QLabel("双手 —")
        self.fps_badge = QLabel("— FPS")
        for badge in (self.face_badge,self.hand_badge,self.fps_badge):
            badge.setObjectName("badge")
            header.addWidget(badge)
        right.addLayout(header)
        self.canvas = canvas_factory()
        self.canvas.show_camera = self.video.isChecked()
        self.canvas.intensity = self.strength.value()/100
        right.addWidget(self.canvas,1)
        self.status = QLabel("离线模型已内置。首次使用时，请允许摄像头访问。")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        right.addWidget(self.status)
        permission_row = QHBoxLayout()
        self.permission_label = QLabel("摄像头权限：检查中")
        self.permission_label.setObjectName("hint")
        permission_row.addWidget(self.permission_label, 1)
        self.permission_settings = QPushButton("打开摄像头设置")
        self.permission_settings.setStyleSheet("padding: 6px 12px;")
        self.permission_settings.clicked.connect(self.open_camera_settings)
        permission_row.addWidget(self.permission_settings)
        right.addLayout(permission_row)
        layout.addWidget(panel,1)
        self.video.toggled.connect(self.set_video)
        self.debug_box.toggled.connect(lambda v: setattr(self.canvas,"debug",v))
        self.sensitivity.valueChanged.connect(self.set_sensitivity)
        self.strength.valueChanged.connect(self.set_intensity)
        self.permissionResult.connect(self.permission_received)
        self.sync_permission()
        self.refresh_devices()
        QApplication.instance().applicationStateChanged.connect(self.application_state_changed)
        if auto_request_permission:
            QTimer.singleShot(300, self.request_initial_permission)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.shortcuts = []
        for key, callback in (("Ctrl+F",self.toggle_fullscreen),("Esc",self.exit_fullscreen),("Space",self.toggle_capture)):
            shortcut = QShortcut(QKeySequence(key),self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    @staticmethod
    def label(layout,text,name):
        label = QLabel(text)
        label.setObjectName(name)
        layout.addWidget(label)
        return label

    @staticmethod
    def divider(layout):
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

    def slider(self,layout,title,low,high,value):
        self.label(layout,title,"hint")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low,high)
        slider.setValue(value)
        layout.addWidget(slider)
        return slider

    def set_mirror(self,value):
        self.options["mirror"] = value
        self.settings.setValue("mirror",value)

    def set_video(self,value):
        self.canvas.show_camera = value
        self.settings.setValue("video",value)

    def set_sensitivity(self,value):
        self.options["sensitivity"] = value/100
        self.settings.setValue("sensitivity",value)

    def set_intensity(self,value):
        self.canvas.intensity = value/100
        self.settings.setValue("intensity",value)

    def refresh_devices(self):
        if self.worker or self.capture_after_permission:
            return
        wanted = self.camera.currentData() or self.settings.value("camera_id","")
        self.camera.clear()
        self.device_enumeration_error = None
        try:
            self.devices = camera_devices()
        except Exception as error:
            LOG.exception("Camera enumeration failed")
            self.device_enumeration_error = str(error)
            self.devices = []
            self.status.setText("设备列表读取失败，请重新打开应用。")
        for index,label,uid in self.devices:
            self.camera.addItem(label,uid)
        selected = self.camera.findData(wanted)
        if selected < 0:
            selected = next((i for i,(_,label,_) in enumerate(self.devices) if any(word in label.lower() for word in ("usb","webcam","logitech","brio"))),0)
        self.camera.setCurrentIndex(selected)
        if not self.devices:
            self.camera.addItem("未发现摄像头，请连接后刷新",None)
        # Authorization must remain reachable even if enumeration is empty.
        self.start_button.setEnabled(bool(self.devices) or self.permission_status != "authorized")

    def sync_permission(self):
        try:
            self.permission_status = camera_permission_status()
        except Exception:
            LOG.exception("Camera authorization status failed")
            self.permission_status = "unknown"
        labels = {"authorized": "已允许", "not_determined": "尚未授权",
                  "denied": "已拒绝，请在设置中开启", "restricted": "受系统策略限制",
                  "unknown": "无法读取", "system_managed": "由 Windows 系统管理"}
        self.permission_label.setText("摄像头权限：" + labels[self.permission_status])
        return self.permission_status

    def application_state_changed(self, state):
        if state != Qt.ApplicationState.ApplicationActive or self.closing:
            return
        previous = self.permission_status
        current = self.sync_permission()
        if not self.worker and not self.permission_pending:
            self.refresh_devices()
            if current == "authorized" and previous != current:
                self.status.setText("摄像头权限已开启。点击“开始互动”即可使用。")
        elif self.worker and current in ("denied", "restricted"):
            self.worker_error = "摄像头权限已关闭。请打开摄像头设置后重新开始。"
            self.stop_capture()

    def open_camera_settings(self):
        # macOS has no public API for granting permission: the user changes it
        # in System Settings. Never reset TCC or automate the permission switch.
        opened = False
        for url in camera_settings_urls():
            if QDesktopServices.openUrl(QUrl(url)):
                opened = True
                break
        if sys.platform == "win32":
            self.status.setText(("请" if opened else "无法打开设置，请手动") +
                "进入 Windows 设置 → 隐私和安全性 → 摄像头，开启摄像头访问和允许桌面应用访问摄像头，然后返回重试。")
            return
        self.status.setText(
            f"请在“隐私与安全性 → 摄像头”中开启“{self.display_name}”，然后返回应用。"
            if opened else "无法打开设置。请手动进入 系统设置 → 隐私与安全性 → 摄像头。")
        if self.permission_status == "restricted":
            self.status.setText("权限受系统策略限制，请检查屏幕使用时间或联系设备管理员。")

    def request_initial_permission(self):
        if self.closing or self.permission_pending:
            return
        state = self.sync_permission()
        if state == "not_determined":
            self.request_permission()
        elif state in ("denied", "restricted"):
            self.show_permission_help()

    def show_permission_help(self):
        self.status.setText(
            "摄像头受系统策略限制，请检查屏幕使用时间或联系设备管理员。"
            if self.permission_status == "restricted" else
            "摄像头访问未获允许。点击“打开摄像头设置”，开启权限后返回应用。")

    def request_permission(self):
        if self.permission_pending:
            return
        self.permission_pending = True
        self.status.setText("正在检查摄像头访问…" if sys.platform == "win32" else
                            "请在系统弹窗中允许摄像头访问。授权不会自动开启摄像头。"
                            if not self.capture_after_permission else "等待摄像头授权…")
        try:
            # AVFoundation may call back on a background queue; marshal to Qt.
            camera_permission(self.permissionResult.emit)
        except Exception as error:
            self.permission_pending = False
            self.capture_after_permission = False
            self.restore_capture_controls()
            self.status.setText(f"摄像头权限检查失败：{error}")

    def restore_capture_controls(self):
        self.start_button.setText("开始互动")
        self.start_button.setEnabled(bool(self.devices) or self.permission_status != "authorized")
        self.camera.setEnabled(True)
        self.refresh.setEnabled(True)
        self.demo_button.setEnabled(True)

    def toggle_capture(self):
        if self.capture_after_permission:
            # A native permission prompt cannot be cancelled by Qt. Cancel only
            # the capture intent; its eventual callback will never start capture.
            self.capture_after_permission = False
            self.restore_capture_controls()
            self.status.setText("已取消开始。")
            return
        if self.worker:
            self.stop_capture()
            return
        state = self.sync_permission()
        if state in ("denied", "restricted"):
            self.show_permission_help()
            return
        if state in ("authorized", "system_managed") and not self.devices:
            self.status.setText("请连接内置或 USB 摄像头，然后刷新设备；也可检查摄像头设置。")
            return
        self.demo = False
        self.canvas.demo = False
        self.canvas.clear()
        self.demo_button.setText("体验演示")
        self.demo_button.setEnabled(False)
        self.camera.setEnabled(False)
        self.refresh.setEnabled(False)
        self.capture_after_permission = True
        self.start_button.setText("取消开始")
        self.request_permission()

    def permission_received(self,allowed):
        if not self.permission_pending or self.closing:
            return
        self.permission_pending = False
        capture_requested = self.capture_after_permission
        self.capture_after_permission = False
        self.sync_permission()
        self.restore_capture_controls()
        if not allowed:
            self.show_permission_help()
            return
        self.refresh_devices()
        if not capture_requested:
            if not self.demo:
                self.status.setText("摄像头权限已开启。点击“开始互动”即可使用。")
            return
        self.start_capture()

    def start_capture(self):
        uid = self.camera.currentData()
        device = next((d for d in self.devices if d[2] == uid),None)
        if device is None:
            self.restore_capture_controls()
            self.status.setText("请连接内置或 USB 摄像头，然后刷新设备。")
            return
        self.settings.setValue("camera_id",uid)
        self.worker_error = None
        self.worker = CameraWorker(device[0],self.options,self)
        self.worker.message.connect(self.status.setText)
        self.worker.failure.connect(self.capture_error)
        self.worker.finished.connect(self.capture_finished)
        self.worker.start()
        self.camera.setEnabled(False)
        self.demo_button.setEnabled(False)
        self.canvas.active = True
        self.start_button.setText("暂停互动")
        self.refresh.setEnabled(False)
        self.calibrate_button.setEnabled(True)

    def capture_error(self,message):
        self.worker_error = message
        self.status.setText(message)

    def stop_capture(self):
        if self.worker:
            self.worker.requestInterruption()
            self.start_button.setEnabled(False)
            self.calibrate_button.setEnabled(False)
            self.status.setText("正在释放摄像头…")

    def capture_finished(self):
        if self.worker:
            self.worker.deleteLater()
        self.worker = None
        self.canvas.clear()
        self.camera.setEnabled(True)
        self.refresh.setEnabled(True)
        self.demo_button.setEnabled(True)
        self.start_button.setText("开始互动")
        self.sync_permission()
        self.start_button.setEnabled(bool(self.devices) or self.permission_status != "authorized")
        self.calibrate_button.setEnabled(False)
        self.status.setText(self.worker_error or "已暂停。点击开始即可继续。")
        if self.closing:
            self.close()

    def toggle_demo(self):
        if self.worker or self.capture_after_permission:
            return
        self.demo = not self.demo
        self.canvas.clear()
        self.canvas.active = self.demo
        self.canvas.demo = self.demo
        self.start_time = time.monotonic()
        self.demo_button.setText("结束演示" if self.demo else "体验演示")
        self.status.setText("正在使用模拟表情与双手数据预览效果，摄像头未开启。" if self.demo else "演示已结束。")

    def calibrate(self):
        if self.worker:
            self.worker.calibration_requested.set()
            self.status.setText("请看向镜头并保持自然表情约两秒。")

    def tick(self):
        if self.worker:
            packet = self.worker.take_packet()
            if packet:
                self.canvas.set_frame(*packet)
        elif self.demo:
            self.canvas.set_frame(QImage(),demo_state(time.monotonic()-self.start_time))
        state = self.canvas.state
        self.emotion.setText(LABELS[state.emotion] if self.canvas.active and state.face else "等待面部")
        if not self.canvas.active:
            self.emotion.setText("等待互动")
        self.face_badge.setText("面部 ✓" if state.face else "面部 —")
        self.hand_badge.setText(f"双手 {len(state.hands)}/2")
        self.fps_badge.setText(f"{state.fps:.0f} FPS" if state.fps else "— FPS")
        self.canvas.animate()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.sidebar.hide()
            self.showFullScreen()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.sidebar.show()

    def closeEvent(self,event):
        self.closing = True
        self.capture_after_permission = False
        self.permission_pending = False
        if self.worker and self.worker.isRunning():
            self.closing = True
            self.stop_capture()
            self.hide()
            event.ignore()
            return
        event.accept()


def verify_models(output):
    import numpy as np
    tracker = Tracker()
    try:
        state = tracker.process(np.zeros((360,640,3),dtype=np.uint8))
        report = {"modelsLoaded":True,"emptyFrameFace":state.face,"emptyFrameHands":len(state.hands),"error":None}
        if state.face is not None or state.hands:
            raise RuntimeError("Empty image unexpectedly produced tracking.")
    finally:
        tracker.close()
    Path(output).write_text(json.dumps(report,indent=2),encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-models",metavar="REPORT")
    parser.add_argument("--smoke-test",metavar="DIRECTORY")
    args = parser.parse_args()
    log_dir = Path.home()/"Library"/"Logs"/"LightInteraction"
    log_dir.mkdir(parents=True,exist_ok=True)
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(log_dir/"app.log",maxBytes=1_000_000,backupCount=2)],format="%(asctime)s %(levelname)s %(message)s")
    if args.verify_models:
        verify_models(args.verify_models)
        return 0
    app = QApplication(sys.argv[:1])
    app.setApplicationName("光感互动")
    app.setOrganizationName("LightInteraction")
    window = Window(auto_request_permission=not bool(args.smoke_test))
    window.canvas.doubleClicked.connect(window.toggle_fullscreen)
    window.show()
    if args.smoke_test:
        destination = Path(args.smoke_test)
        destination.mkdir(parents=True,exist_ok=True)
        QTimer.singleShot(100,window.toggle_demo)
        def capture():
            window.grab().save(str(destination/"app-preview.png"))
            window.toggle_fullscreen()
            QTimer.singleShot(400,finish)
        def finish():
            window.canvas.grab().save(str(destination/"fullscreen-preview.png"))
            window.exit_fullscreen()
            report = {"guiReady":window.isVisible(),"demoHands":len(window.canvas.state.hands),
                      "particleCount":len(window.canvas.particles),"fullscreenExited":not window.isFullScreen(),
                      "cameraDevices":[d[1] for d in window.devices],"error":None}
            (destination/"gui-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            window.close()
        QTimer.singleShot(1800,capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
