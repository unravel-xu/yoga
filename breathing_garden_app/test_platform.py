"""Cross-platform contract tests. No system setting changes or camera capture."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from interactive_app import engine, platform_support as native
from breathing_garden_app.test_app import WindowTests as _WindowFixture


class NativePlatformTests(unittest.TestCase):
    def test_windows_permission_is_not_falsely_authorized(self):
        callback = Mock()
        with patch.object(sys,"platform","win32"):
            self.assertEqual(engine.camera_permission_status(),"system_managed")
            engine.camera_permission(callback)
        callback.assert_called_once_with(True)

    def test_windows_dshow_devices_preserve_backend_indices(self):
        graph = SimpleNamespace(get_input_devices=lambda:["Integrated Camera","USB Webcam"])
        fake = SimpleNamespace(FilterGraph=lambda:graph)
        with patch.dict(sys.modules,{"pygrabber.dshow_graph":fake}):
            devices = native.windows_camera_devices()
        self.assertEqual([d[0] for d in devices],[0,1])
        self.assertEqual(devices[1][1],"USB Webcam")
        self.assertNotEqual(devices[0][2],devices[1][2])

    def test_windows_backend_settings_and_paths(self):
        import cv2
        with patch.object(sys,"platform","win32"), patch.dict("os.environ",{"LOCALAPPDATA":"C:/测试用户/Local"}):
            self.assertEqual(native.capture_backend(),cv2.CAP_DSHOW)
            self.assertEqual(native.camera_settings_urls()[0],"ms-settings:privacy-webcam")
            self.assertEqual(native.app_directory("logs"),Path("C:/测试用户/Local/BreathingGarden/Logs"))

    def test_mac_backend_unchanged(self):
        import cv2
        with patch.object(sys,"platform","darwin"):
            self.assertEqual(native.capture_backend(),cv2.CAP_AVFOUNDATION)
            self.assertIn("Privacy_Camera",native.camera_settings_urls()[0])

    def test_models_use_bytes_for_unicode_paths(self):
        # Both model constructors must receive bytes, not MediaPipe's Windows
        # narrow-string path API. Real native inference is checked by CI.
        face,hand = Mock(),Mock()
        with patch.object(engine,"model_path") as path, \
             patch.object(engine.vision.FaceLandmarker,"create_from_options",return_value=face) as make_face, \
             patch.object(engine.vision.HandLandmarker,"create_from_options",return_value=hand) as make_hand:
            path.return_value.read_bytes.return_value = b"test-model"
            tracker = engine.Tracker()
            for factory in (make_face,make_hand):
                opts = factory.call_args.args[0].base_options
                self.assertEqual(opts.model_asset_buffer,b"test-model")
                self.assertIsNone(opts.model_asset_path)
            tracker.close()


class WindowsWindowTests(unittest.TestCase):
    setUpClass = classmethod(_WindowFixture.setUpClass.__func__)
    setUp = _WindowFixture.setUp
    tearDown = _WindowFixture.tearDown

    def test_windows_system_managed_can_start(self):
        from interactive_app import app as ui
        self.window.permission_status = "system_managed"
        self.window.update_guide()
        self.assertIn("开始互动",self.window.guide_hint.text())
        with patch.object(ui,"camera_permission_status",return_value="system_managed"), \
             patch.object(ui,"camera_permission",side_effect=lambda cb:cb(True)), \
             patch.object(self.window,"start_capture") as start:
            self.window.toggle_capture()
            start.assert_called_once()

    def test_windows_settings_uri_and_help(self):
        from interactive_app import app as ui
        with patch.object(sys,"platform","win32"), \
             patch.object(ui.QDesktopServices,"openUrl",return_value=True) as opened:
            self.window.open_camera_settings()
            self.assertEqual(opened.call_args.args[0].toString(),"ms-settings:privacy-webcam")
            self.assertIn("允许桌面应用",self.window.status.text())


del _WindowFixture


if __name__ == "__main__":
    unittest.main()
