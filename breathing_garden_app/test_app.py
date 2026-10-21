"""Offline regression tests; never request camera access or capture images."""
import time
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtGui import QImage
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from interactive_app.engine import Hand,Tracking
from breathing_garden_app.tracking import TrackingBridge
from breathing_garden_app.canvas import GardenCanvas,visible_color
from breathing_garden_app.app import GardenWindow


def hand(label="Right",pinch=0):
    points = [(.5,.5)]*21
    points[0] = (.5,.8)
    points[9] = (.5,.6)
    points[6] = (.5,.5)
    points[8] = (.5,.3)
    points[4] = (.36,.5)
    return Hand(label,.43,.4,pinch,.8,points=points)


class TrackingTests(unittest.TestCase):
    def test_display_color_lift_preserves_transparent_fade(self):
        color = visible_color((.3,.7,.6,.4))
        self.assertGreater(color.greenF(),.7)
        self.assertGreater(color.alphaF(),.4)
        self.assertGreater(color.greenF(),color.redF())
        self.assertEqual(visible_color((.3,.7,.6,0)).alphaF(),0)
        self.assertLess(visible_color((.3,.7,.6,.02)).alphaF(),.04)

    def test_uses_index_tip_not_midpoint_and_top_down_y(self):
        bridge = TrackingBridge()
        data = bridge.convert(Tracking(hands=[hand()]))
        self.assertEqual(data["tip_u"],.5)
        self.assertEqual(data["tip_v"],.3)
        self.assertEqual(data["draw"],1)

    def test_pinch_hysteresis(self):
        bridge = TrackingBridge()
        for pinch,expected in ((.8,1),(.65,1),(.54,0),(.65,0)):
            data = bridge.convert(Tracking(hands=[hand(pinch=pinch)]))
            self.assertEqual(data["pinch"],expected)

    def test_hand_switch_inserts_lost_frame(self):
        bridge = TrackingBridge()
        bridge.convert(Tracking(hands=[hand("Right")]))
        self.assertEqual(bridge.convert(Tracking(hands=[hand("Left")]))["tracked"],0)
        self.assertEqual(bridge.convert(Tracking(hands=[hand("Left")]))["tracked"],1)

    def test_face_without_hand_still_drives_breath(self):
        data = TrackingBridge().convert(Tracking(face=(.5,.5,.2),mouth=.6,smile=.7))
        self.assertEqual(data["tracked"],0)
        self.assertEqual(data["mouth"],.6)
        self.assertEqual(data["smile"],.7)

    def test_nan_and_missing_landmarks_safe(self):
        h = hand()
        h.points[8] = (float("nan"),.2)
        self.assertEqual(TrackingBridge().convert(Tracking(hands=[h]))["tracked"],0)
        h.points = []
        self.assertEqual(TrackingBridge().convert(Tracking(hands=[h]))["tracked"],0)


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="garden-ui-tests-")
        self.test_settings = QSettings(self.temp.name+"/settings.ini",QSettings.Format.IniFormat)
        self.mocks = [patch("interactive_app.app.camera_devices",return_value=[(0,"Test Camera","test-id")]),
                      patch("interactive_app.app.camera_permission_status",return_value="authorized"),
                      patch("interactive_app.app.QSettings",return_value=self.test_settings)]
        for mock in self.mocks:
            mock.start()
        self.window = GardenWindow(auto_request_permission=False)
        self.window.timer.stop()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        for mock in reversed(self.mocks):
            mock.stop()
        self.test_settings.sync()
        self.temp.cleanup()

    def test_idle_and_demo_render(self):
        self.window.show()
        self.window.toggle_demo()
        c = self.window.canvas
        for _ in range(90):
            c.last_tick -= 1/30
            self.window.tick()
        self.assertGreater(c.world.segment_count,0)
        self.assertFalse(c.grab().isNull())
        self.assertIsNone(self.window.worker)

    def test_stop_preserves_world_and_autonomous_growth(self):
        c = self.window.canvas
        for _ in range(30):
            c.world.advance(1/30,dict(tip_u=.4,tip_v=.5,tracked=1,draw=1))
        count = c.world.segment_count
        identity = c.world
        c.clear()
        self.assertIs(c.world,identity)
        for _ in range(30):
            c.last_tick -= 1/30
            c.animate()
        self.assertGreater(c.world.segment_count,count)

    def test_stale_frame_disconnects(self):
        c = self.window.canvas
        c.active = True
        state = Tracking(hands=[hand()],captured_at=time.monotonic()-1)
        c.set_frame(QImage(),state)
        c.last_tick -= .1
        c.animate()
        self.assertFalse(c.world.tracked)

    def test_fullscreen_has_only_art_and_restores_controls(self):
        self.window.show()
        self.window.canvas.show_camera = True
        self.window.canvas.debug = True
        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertTrue(all(w.isHidden() for w,_ in self.window._chrome))
        self.assertFalse(self.window.canvas.show_camera)
        self.assertFalse(self.window.canvas.debug)
        self.window.exit_fullscreen()
        self.assertTrue(self.window.canvas.show_camera)
        self.assertTrue(self.window.canvas.debug)
        self.assertFalse(self.window.guide_panel.isHidden())

    def test_guide_toggle_persists_and_stays_hidden_fullscreen(self):
        self.window.show()
        self.assertTrue(self.window.guide_visible)
        self.window.guide_button.click()
        self.assertTrue(self.window.guide_panel.isHidden())
        self.assertFalse(self.test_settings.value("show_guide",True,type=bool))
        self.window.toggle_fullscreen()
        self.window.toggle_guide()
        self.assertTrue(self.window.guide_panel.isHidden())
        self.window.exit_fullscreen()
        self.assertFalse(self.window.guide_panel.isHidden())

    def test_guide_tracks_dwell_and_pinch(self):
        self.window.worker = object()
        w = self.window.canvas.world
        w.tracked = True
        w.draw_gate.value = True
        w.dwell_time = w.config.DWELL_SECONDS*.5
        self.window.update_guide()
        self.assertEqual(self.window.dwell_progress.value(),50)
        w.pinch_gate.value = True
        self.window.update_guide()
        self.assertIn("松开",self.window.guide_hint.text())
        self.assertEqual(self.window.dwell_progress.value(),0)
        self.window.worker = None

    def test_brightness_range_and_label(self):
        self.window.strength.setValue(180)
        self.assertAlmostEqual(self.window.canvas.intensity,1.8)
        self.assertIn("180%",self.window.brightness_label.text())
        self.assertEqual(self.window.strength.maximum(),220)

    def test_low_quality_and_reset(self):
        self.window.set_quality("LOW")
        self.assertEqual(len(self.window.canvas.world.dust),150)
        self.window.reset_button.click()
        self.assertEqual(self.window.canvas.quality,"LOW")


if __name__ == "__main__":
    unittest.main()
