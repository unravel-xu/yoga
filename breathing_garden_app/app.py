"""Standalone garden window; reuse the tested capture/permission lifecycle."""
import argparse
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QComboBox,
                              QHBoxLayout, QVBoxLayout, QFrame, QProgressBar)

from interactive_app.app import Window, verify_models
from interactive_app.platform_support import app_directory
from breathing_garden_app.canvas import GardenCanvas
from breathing_garden_app.resources import load_ui_font


class GardenWindow(Window):
    def __init__(self,auto_request_permission=True):
        super().__init__(auto_request_permission=auto_request_permission,
                         canvas_factory=GardenCanvas,settings_name="BreathingGarden",
                         display_name="呼吸的花园 / Breathing Garden")
        self.setWindowTitle("呼吸的花园 · The Breathing Garden")
        self.findChild(QLabel,"eyebrow").setText("THE BREATHING GARDEN")
        self.findChild(QLabel,"title").setText("呼吸的花园")
        self.findChild(QLabel,"subtitle").setText("食指播种 · 停留开花 · 呼吸生长")
        replacements = {"表情灵敏度":"面部动作响应", "光效强度":"生命亮度",
                        "捏合爆发 · 张掌扩环 · 挥手拖尾\nEsc 退出全屏 · 空格开始/暂停":
                        "伸出食指绘制 · 停留开花\n捏合后松开消散 · 双击画面全屏"}
        for label in self.sidebar.findChildren(QLabel):
            if label.text() in replacements:
                label.setText(replacements[label.text()])
        self.brightness_label = next(label for label in self.sidebar.findChildren(QLabel)
                                     if label.text()=="生命亮度")
        self.strength.setRange(30,220)
        self.strength.setToolTip("默认100%；可提高至220%，增强花园亮度。")
        self.strength.valueChanged.connect(self.update_brightness_label)
        self.update_brightness_label(self.strength.value())
        self.calibrate_button.hide()
        self.video.setText("显示摄像头（仅测试）")
        self.video.setChecked(self.settings.value("video",False,type=bool))
        self.debug_box.setText("显示骨架与指尖（仅测试）")
        self.demo_button.setText("模拟输入演示")
        self.quality = QComboBox()
        self.quality.addItems(["NORMAL","LOW"])
        self.quality.setCurrentText(self.settings.value("quality","NORMAL"))
        self.canvas.reset_world(self.quality.currentText())
        self.quality.currentTextChanged.connect(self.set_quality)
        self.reset_button = QPushButton("重置花园")
        self.reset_button.clicked.connect(self.canvas.reset_world)
        row = QHBoxLayout()
        row.addWidget(self.quality)
        row.addWidget(self.reset_button)
        self.sidebar.layout().insertLayout(self.sidebar.layout().indexOf(self.calibrate_button),row)
        self.metrics_label = QLabel()
        self.metrics_label.setObjectName("hint")
        self.metrics_label.setWordWrap(True)
        self.canvas.parentWidget().layout().addWidget(self.metrics_label)
        self.guide_visible = self.settings.value("show_guide",True,type=bool)
        self.create_guide()
        self._chrome = []
        self._preview_options = None
        self.status.setText("允许摄像头访问后，点击“开始互动”。不需启动 TouchDesigner；画面不录制、不上传。")
        self.canvas.doubleClicked.connect(self.toggle_fullscreen)

    def update_brightness_label(self,value):
        self.brightness_label.setText(f"生命亮度 · {value}%")

    def create_guide(self):
        panel = self.canvas.parentWidget()
        self.guide_panel = QFrame()
        self.guide_panel.setObjectName("interactionGuide")
        self.guide_panel.setStyleSheet("QFrame#interactionGuide { background: #142a2e; border: 1px solid #315454; border-radius: 10px; }")
        layout = QVBoxLayout(self.guide_panel)
        layout.setContentsMargins(14,10,14,10)
        layout.setSpacing(8)
        steps = QHBoxLayout()
        steps.setSpacing(18)
        self.guide_titles = []
        self._guide_step = None
        for title,description in (
            ("01  食指绘制","伸直食指，慢慢移动，让枝条沿轨迹生长。"),
            ("02  停留开花","指尖停在一处约0.8秒，等待六瓣花展开。"),
            ("03  捏合后松开","靠近枝条捏合片刻，再松开，让它散成微光。")):
            column = QVBoxLayout()
            column.setSpacing(4)
            heading = QLabel(title)
            heading.setStyleSheet("color: #B4F4DC; font-size: 13px; font-weight: 600;")
            detail = QLabel(description)
            detail.setWordWrap(True)
            detail.setStyleSheet("color: #B4C9C9; font-size: 12px;")
            self.guide_titles.append(heading)
            column.addWidget(heading)
            column.addWidget(detail)
            steps.addLayout(column,1)
        layout.addLayout(steps)
        row = QHBoxLayout()
        self.guide_hint = QLabel("允许摄像头权限，然后点击“开始互动”。")
        self.guide_hint.setWordWrap(True)
        self.guide_hint.setStyleSheet("color: #93BEAF; font-size: 12px;")
        row.addWidget(self.guide_hint,1)
        self.dwell_progress = QProgressBar()
        self.dwell_progress.setRange(0,100)
        self.dwell_progress.setValue(0)
        self.dwell_progress.setTextVisible(False)
        self.dwell_progress.setFixedSize(78,5)
        self.dwell_progress.setToolTip("停留开花进度")
        self.dwell_progress.setStyleSheet("QProgressBar { background: #223F42; border: none; border-radius: 2px; } QProgressBar::chunk { background: #8FE8C0; border-radius: 2px; }")
        row.addWidget(self.dwell_progress)
        layout.addLayout(row)
        panel.layout().insertWidget(1,self.guide_panel)
        self.guide_button = QPushButton()
        self.guide_button.setStyleSheet("padding: 6px 10px;")
        self.guide_button.setToolTip("显示/隐藏互动指引 · H")
        self.guide_button.clicked.connect(self.toggle_guide)
        panel.layout().itemAt(0).layout().addWidget(self.guide_button)
        self.guide_shortcut = QShortcut(QKeySequence("H"),self)
        self.guide_shortcut.activated.connect(self.toggle_guide)
        self.apply_guide_visibility()

    def apply_guide_visibility(self):
        self.guide_panel.setVisible(self.guide_visible and not self.isFullScreen())
        self.guide_button.setText("隐藏指引" if self.guide_visible else "互动指引")

    def toggle_guide(self):
        self.guide_visible = not self.guide_visible
        self.settings.setValue("show_guide",self.guide_visible)
        self.apply_guide_visibility()

    def update_guide(self):
        w = self.canvas.world
        progress = 0
        step = -1
        if self.demo:
            text = "当前为模拟演示；点击“开始互动”即可切换到真实摄像头。"
        elif self.permission_status not in ("authorized", "system_managed"):
            text = "先允许摄像头访问；已拒绝时，请点击下方“打开摄像头设置”。"
        elif not self.worker:
            text = "点击“开始互动”，让脸和整只手进入镜头；微笑变暖，张嘴增强呼吸。"
        elif not w.tracked:
            text = "将整只手和手腕放入镜头，伸直食指；可打开“显示骨架与指尖”检查识别。"
        elif w.pinch_gate.value:
            step = 2
            text = "保持捏合片刻，再在枝条附近松开；光点将缓慢散开。"
        elif w.dwell_fired:
            step = 1
            progress = 100
            text = "已触发开花。移动一小段后再次停留，可以继续播种小花。"
        elif w.draw_gate.value:
            step = 0
            progress = min(100,round(w.dwell_time/w.config.DWELL_SECONDS*100))
            text = "食指正在绘制。慢慢移动播种；停下来保持约0.8秒，进度满后开花。"
        else:
            step = 0
            text = "手部已识别：伸直食指缓慢移动，或靠近已有枝条尝试捏合后松开。"
        if self.guide_hint.text()!=text:
            self.guide_hint.setText(text)
        self.dwell_progress.setValue(progress)
        if self._guide_step!=step:
            self._guide_step = step
            for index,title in enumerate(self.guide_titles):
                title.setStyleSheet("color: %s; font-size: 13px; font-weight: 600;" %
                                   ("#E5FFF0" if index==step else "#9BC9B7"))

    def set_quality(self,value):
        self.settings.setValue("quality",value)
        self.canvas.reset_world(value)
        self.status.setText(f"已切换 {value}，花园已重置。")

    def toggle_demo(self):
        if self.worker or self.capture_after_permission:
            return
        self.demo = not self.demo
        self.canvas.clear()
        self.canvas.demo = self.demo
        self.canvas.active = self.demo
        self.demo_button.setText("结束模拟演示" if self.demo else "模拟输入演示")
        self.status.setText("TEST_MODE：模拟绘制、停留和捏合，摄像头未开启。" if self.demo else "模拟已结束，已有生命继续生长。")

    def tick(self):
        if self.worker:
            packet = self.worker.take_packet()
            if packet:
                self.canvas.set_frame(*packet)
        self.canvas.animate()
        self.update_guide()
        w = self.canvas.world
        if w.tracked:
            gesture = "捏合中" if w.pinch_gate.value else "停留开花" if w.dwell_fired else "食指绘制" if w.draw_gate.value else "手部已识别"
        else:
            gesture = "等待手部入镜" if self.worker else "安静生长"
        self.emotion.setText(gesture)
        self.face_badge.setText("面部 ✓" if self.canvas.state.face and self.canvas.tracking_fresh() else "面部 —")
        self.hand_badge.setText("TEST_MODE" if self.demo else f"手部 {len(self.canvas.state.hands) if w.tracked else 0}/2")
        self.fps_badge.setText(f"{self.canvas.render_fps:.0f} FPS")
        metrics = w.diagnostics()
        quality = "自动 LOW" if self.canvas.degraded else self.canvas.quality
        self.metrics_label.setText(
            f"植物 {metrics['plants']}/9  ·  枝条 {metrics['segments']}  ·  花 {metrics['flowers']}  ·  微光 {metrics['particles']}  ·  {quality}\n"
            f"识别 {self.canvas.state.fps:.0f} FPS  ·  绘制 {self.canvas.paint_ms:.1f} ms  ·  mouth {w.mouth:.2f}  ·  smile {w.smile:.2f}")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
            return
        panel = self.canvas.parentWidget()
        self._chrome = [(widget,not widget.isHidden()) for widget in panel.findChildren(QLabel)]
        self._chrome.extend((widget,not widget.isHidden()) for widget in
                            (self.permission_settings,self.guide_button,self.guide_panel))
        for widget,_ in self._chrome:
            widget.hide()
        self._preview_options = (self.canvas.show_camera,self.canvas.debug)
        self.canvas.show_camera = self.canvas.debug = False
        panel.layout().setContentsMargins(0,0,0,0)
        panel.layout().setSpacing(0)
        self.sidebar.hide()
        self.showFullScreen()

    def exit_fullscreen(self):
        if not self.isFullScreen():
            return
        self.showNormal()
        self.sidebar.show()
        for widget,visible in self._chrome:
            widget.setVisible(visible)
        if self._preview_options:
            self.canvas.show_camera,self.canvas.debug = self._preview_options
        panel = self.canvas.parentWidget()
        panel.layout().setContentsMargins(20,20,20,16)
        panel.layout().setSpacing(12)
        self.apply_guide_visibility()


def main():
    parser = argparse.ArgumentParser(description="The Breathing Garden · Offline camera app")
    parser.add_argument("--smoke-test",metavar="DIRECTORY")
    parser.add_argument("--verify-models",metavar="REPORT")
    args = parser.parse_args()
    log_dir = app_directory("logs")
    log_dir.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,
        handlers=[RotatingFileHandler(log_dir/"app.log",maxBytes=1_000_000,backupCount=2,encoding="utf-8")],
        format="%(asctime)s %(levelname)s %(message)s")
    if args.verify_models:
        verify_models(args.verify_models)
        return 0
    trace_file = None
    if args.smoke_test:
        trace_file = (log_dir/"smoke-trace.txt").open("w",encoding="utf-8")
        faulthandler.dump_traceback_later(20,repeat=True,file=trace_file)
    logging.info("Starting Qt application")
    app = QApplication(sys.argv[:1])
    logging.info("Registering bundled UI font")
    try:
        font_report = load_ui_font(app)
    except Exception:
        logging.exception("UI font initialization failed")
        if args.smoke_test:
            # PyInstaller's windowed exception dialog would block CI forever.
            faulthandler.cancel_dump_traceback_later()
            return 2
        raise
    logging.info("UI font ready: %s",font_report)
    app.setApplicationName("呼吸的花园")
    app.setOrganizationName("BreathingGarden")
    window = GardenWindow(auto_request_permission=not bool(args.smoke_test))
    logging.info("Window initialized")
    window.show()
    if args.smoke_test:
        folder = Path(args.smoke_test)
        folder.mkdir(parents=True,exist_ok=True)
        def begin():
            window.toggle_demo()
            # Deterministic pre-roll of the actual shared simulation, not a
            # video or fixed screenshot. The remaining frames animate normally.
            from breathing_garden_td.garden_engine import test_tracking
            for i in range(30*10):
                window.canvas.world.advance(1/30,test_tracking(i/30))
        def capture():
            logging.info("Smoke screenshot capture")
            window.grab().save(str(folder/"app-preview.png"))
            window.toggle_fullscreen()
            QTimer.singleShot(300,finish)
        def finish():
            window.canvas.grab().save(str(folder/"garden-preview.png"))
            hidden = all(widget.isHidden() for widget,_ in window._chrome)
            window.exit_fullscreen()
            report = {"ok":True,"world":window.canvas.world.diagnostics(),
                      "camera_started":window.worker is not None,
                      "fullscreen_chrome_hidden":hidden,"fullscreen_exited":not window.isFullScreen(),
                      "render_fps":window.canvas.render_fps,"paint_ms":window.canvas.paint_ms,
                      "device_enumeration_error":window.device_enumeration_error,
                      "font":font_report,
                      "devices":[d[1] for d in window.devices]}
            (folder/"app-test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            window.close()
            logging.info("Smoke test complete")
        QTimer.singleShot(100,begin)
        QTimer.singleShot(1800,capture)
    result = app.exec()
    if trace_file:
        faulthandler.cancel_dump_traceback_later()
        trace_file.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
