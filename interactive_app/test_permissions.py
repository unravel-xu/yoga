"""Permission flow regression tests; no camera, TCC prompts or settings writes.

Run: QT_QPA_PLATFORM=offscreen interactive_app/.venv/bin/python -m unittest
     interactive_app.test_permissions -v
"""
import unittest
import inspect
import sys
from types import SimpleNamespace
from unittest.mock import patch, Mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from interactive_app import app as ui
from interactive_app import engine


class PermissionFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.state = "not_determined"
        self.callbacks = []
        self.patches = [
            patch.object(ui, "camera_permission_status", side_effect=lambda: self.state),
            patch.object(ui, "camera_devices", return_value=[(0, "Test Camera", "test-id")]),
            patch.object(ui, "camera_permission", side_effect=self.callbacks.append),
        ]
        for mock in self.patches:
            mock.start()
        self.window = ui.Window(auto_request_permission=False)
        self.window.timer.stop()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        for mock in reversed(self.patches):
            mock.stop()

    def resolve(self, allowed):
        self.state = "authorized" if allowed else "denied"
        self.callbacks.pop(0)(allowed)
        self.application.processEvents()

    def test_startup_requests_once_without_starting_camera(self):
        with patch.object(self.window, "start_capture") as start:
            self.window.request_initial_permission()
            self.window.request_initial_permission()
            self.assertEqual(len(self.callbacks), 1)
            self.resolve(True)
            start.assert_not_called()
            self.assertIn("已允许", self.window.permission_label.text())

    def test_denied_does_not_prompt_again_and_has_help(self):
        self.state = "denied"
        self.window.request_initial_permission()
        self.window.toggle_capture()
        self.assertFalse(self.callbacks)
        self.assertIn("打开摄像头设置", self.window.status.text())
        self.assertTrue(self.window.permission_settings.isEnabled())

    def test_settings_link_and_fallback(self):
        with patch("interactive_app.platform_support.sys.platform", "darwin"), patch.object(ui.QDesktopServices, "openUrl", return_value=True) as opened:
            self.window.permission_settings.click()
            self.assertEqual(opened.call_args.args[0].toString(),
                             "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera")
        with patch.object(ui.QDesktopServices, "openUrl", side_effect=[False, False]) as opened:
            self.window.open_camera_settings()
            self.assertEqual(opened.call_count, 2)
            self.assertIn("手动", self.window.status.text())

    def test_cancelled_request_late_callback_never_captures(self):
        with patch.object(self.window, "start_capture") as start:
            self.window.toggle_capture()
            self.assertFalse(self.window.refresh.isEnabled())
            self.window.toggle_capture()
            self.assertTrue(self.window.refresh.isEnabled())
            self.resolve(True)
            start.assert_not_called()

    def test_start_during_startup_reuses_prompt(self):
        with patch.object(self.window, "start_capture") as start:
            self.window.request_initial_permission()
            self.window.toggle_capture()
            self.assertEqual(len(self.callbacks), 1)
            self.resolve(True)
            start.assert_called_once()

    def test_return_from_settings_updates_status(self):
        self.state = "denied"
        self.window.sync_permission()
        self.state = "authorized"
        self.window.application_state_changed(Qt.ApplicationState.ApplicationActive)
        self.assertIn("已允许", self.window.permission_label.text())
        self.assertIn("权限已开启", self.window.status.text())

    def test_restricted_explains_policy(self):
        self.state = "restricted"
        self.window.request_initial_permission()
        self.assertIn("设备管理员", self.window.status.text())
        self.assertFalse(self.callbacks)

    def test_no_device_still_requests_permission(self):
        with patch.object(ui, "camera_devices", return_value=[]):
            self.window.refresh_devices()
            self.assertTrue(self.window.start_button.isEnabled())
            self.window.toggle_capture()
            self.assertEqual(len(self.callbacks), 1)
            self.resolve(True)
            self.assertIsNone(self.window.worker)
            self.assertIn("连接", self.window.status.text())

    def test_closed_window_does_not_request_or_start(self):
        with patch.object(self.window, "start_capture") as start:
            self.window.toggle_capture()
            self.window.close()
            self.resolve(True)
            self.window.request_initial_permission()
            self.assertFalse(self.callbacks)
            start.assert_not_called()

    def test_native_boundary_wraps_qt_emit_in_python_function(self):
        request = Mock()
        av = SimpleNamespace(AVAuthorizationStatusNotDetermined=0,
                             AVAuthorizationStatusAuthorized=3, AVMediaTypeVideo="video",
                             AVCaptureDevice=SimpleNamespace(
                                 authorizationStatusForMediaType_=Mock(return_value=0),
                                 requestAccessForMediaType_completionHandler_=request))
        with patch.object(engine.sys, "platform", "darwin"), patch.dict(sys.modules, {"AVFoundation": av}):
            engine.camera_permission(self.window.permissionResult.emit)
            completion = request.call_args.args[1]
            self.assertTrue(inspect.isfunction(completion))
            completion(True)


if __name__ == "__main__":
    unittest.main()
