"""Offline MediaPipe inference and persistent hand/expression controls."""
from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from interactive_app.platform_support import windows_camera_devices
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

PALETTES = {
    "calm": (66, 177, 255), "joy": (255, 92, 170),
    "surprise": (68, 244, 233), "anger": (255, 113, 65),
    "sad": (156, 129, 255),
}
LABELS = {"calm": "平静", "joy": "微笑", "surprise": "惊讶", "anger": "皱眉", "sad": "低落"}
HAND_EDGES = ((0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
              (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),
              (15,16),(13,17),(0,17),(17,18),(18,19),(19,20))


def model_path(name):
    root = Path(sys._MEIPASS) / "interactive_app" if getattr(sys, "frozen", False) else Path(__file__).parent
    return root / "models" / name


def clamp(x, low=0.0, high=1.0):
    return max(low, min(high, x))


def mapped(x, low, high):
    return clamp((x - low) / (high - low))


@dataclass
class Hand:
    label: str
    x: float
    y: float
    pinch: float
    openness: float
    speed: float = 0.0
    burst: float = 0.0
    points: list = field(default_factory=list)


@dataclass
class Tracking:
    face: tuple | None = None
    emotion: str = "calm"
    strength: float = 0.0
    hands: list[Hand] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    fps: float = 0.0
    mouth: float = 0.0
    smile: float = 0.0
    captured_at: float = 0.0


class Tracker:
    def __init__(self):
        self.face_model = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_buffer=model_path("face_landmarker.task").read_bytes()),
            running_mode=vision.RunningMode.VIDEO, num_faces=1,
            output_face_blendshapes=True, min_face_detection_confidence=0.45,
            min_face_presence_confidence=0.45, min_tracking_confidence=0.45,
        ))
        try:
            self.hand_model = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_buffer=model_path("hand_landmarker.task").read_bytes()),
                running_mode=vision.RunningMode.VIDEO, num_hands=2,
                min_hand_detection_confidence=0.45, min_hand_presence_confidence=0.45,
                min_tracking_confidence=0.45,
            ))
        except Exception:
            self.face_model.close()
            raise
        self.last_time = time.monotonic()
        self.timestamp = 0
        self.scores = dict.fromkeys(("joy", "surprise", "anger", "sad"), 0.0)
        self.emotion = "calm"
        self.hold_until = 0.0
        self.previous = {}
        self.face_position = None
        self.baseline = {}
        self.calibration_samples = []
        self.calibrating_until = 0.0

    def close(self):
        self.face_model.close()
        self.hand_model.close()

    def calibrate(self):
        self.calibration_samples = []
        self.calibrating_until = time.monotonic() + 1.8

    def process(self, rgb, sensitivity=1.0):
        now = time.monotonic()
        dt = max(0.001, min(0.2, now - self.last_time))
        self.last_time = now
        self.timestamp = max(self.timestamp + 1, int(now * 1000))
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        face = self.face_model.detect_for_video(image, self.timestamp)
        hands = self.hand_model.detect_for_video(image, self.timestamp)
        state = Tracking(captured_at=now)
        raw = dict.fromkeys(self.scores, 0.0)
        if face.face_landmarks:
            points = face.face_landmarks[0]
            tip = points[1]
            if self.face_position is None:
                self.face_position = (tip.x, tip.y)
            a = 1 - math.exp(-dt / 0.10)
            self.face_position = tuple(old + a * (new - old) for old, new in zip(self.face_position, (tip.x, tip.y)))
            # Face width provides scale for effects as the visitor approaches.
            state.face = (*self.face_position, abs(points[454].x - points[234].x))
            blend = {c.category_name: c.score for c in face.face_blendshapes[0]} if face.face_blendshapes else {}
            if self.calibrating_until:
                self.calibration_samples.append(blend)
            def value(name):
                return max(0.0, blend.get(name, 0.0) - self.baseline.get(name, 0.0))
            def pair(name):
                return (value(name + "Left") + value(name + "Right")) * 0.5
            # Continuous visible actions for the garden, not emotion labels.
            state.mouth = clamp(value("jawOpen") * sensitivity)
            state.smile = clamp(pair("mouthSmile") * sensitivity)
            raw = {
                "joy": mapped(pair("mouthSmile") * sensitivity, .18, .72),
                "surprise": mapped((value("jawOpen") * .62 + pair("eyeWide") * .38) * sensitivity, .22, .72),
                "anger": mapped((pair("browDown") * .72 + pair("noseSneer") * .28) * sensitivity, .25, .70),
                "sad": mapped((pair("mouthFrown") * .68 + value("browInnerUp") * .32) * sensitivity, .23, .66),
            }
        else:
            self.face_position = None
        if self.calibrating_until and now >= self.calibrating_until:
            if self.calibration_samples:
                keys = self.calibration_samples[0]
                self.baseline = {k: float(np.mean([s.get(k, 0) for s in self.calibration_samples])) for k in keys}
            self.calibrating_until = 0.0
        a = 1 - math.exp(-dt / .16)
        self.scores = {k: old + a * (raw[k] - old) for k, old in self.scores.items()}
        candidate = max(self.scores, key=self.scores.get)
        if self.scores[candidate] < .18:
            candidate = "calm"
        if candidate != self.emotion and now >= self.hold_until:
            if candidate == "calm" or self.scores[candidate] > self.scores.get(self.emotion, 0) + .10:
                self.emotion = candidate
                self.hold_until = now + .28
        state.emotion = self.emotion
        state.strength = self.scores.get(self.emotion, .15) if state.face else 0.0
        state.scores = self.scores.copy()
        seen = set()
        aspect = rgb.shape[1] / rgb.shape[0]
        for index, landmarks in enumerate(hands.hand_landmarks):
            category = hands.handedness[index][0]
            label = category.category_name
            seen.add(label)
            points = [(p.x, p.y) for p in landmarks]
            def dist(i, j):
                return math.hypot((points[i][0] - points[j][0]) * aspect, points[i][1] - points[j][1])
            scale = max(.035, dist(0, 9))
            pinch = 1.0 - mapped(dist(4, 8) / scale, .18, 1.10)
            openness = mapped(sum(dist(0, i) / scale for i in (4,8,12,16,20)) / 5, 1.15, 2.25)
            x, y = (points[4][0] + points[8][0]) * .5, (points[4][1] + points[8][1]) * .5
            previous = self.previous.get(label)
            hand = Hand(label, x, y, pinch, openness, points=points)
            if previous is not None:
                hand.speed = clamp(math.hypot((x-previous.x)*aspect, y-previous.y) / dt * .25)
                if (pinch > .78 >= previous.pinch) or (openness > .82 and previous.openness <= .55):
                    hand.burst = 1.0
                else:
                    hand.burst = previous.burst * math.exp(-4.2 * dt)
                a = 1 - math.exp(-dt / .065)
                hand.x = previous.x + a * (x - previous.x)
                hand.y = previous.y + a * (y - previous.y)
            self.previous[label] = hand
            state.hands.append(hand)
        self.previous = {k: v for k, v in self.previous.items() if k in seen}
        return state


def camera_devices():
    """Use the same AVFoundation order as OpenCV's macOS capture backend."""
    if sys.platform == "win32":
        return windows_camera_devices()
    import AVFoundation as av
    devices = av.AVCaptureDevice.devicesWithMediaType_(av.AVMediaTypeVideo)
    return [(index, str(device.localizedName()), str(device.uniqueID())) for index, device in enumerate(devices)]


def camera_permission_status():
    """Read TCC authorization without opening a camera or displaying a prompt."""
    if sys.platform == "win32":
        # A desktop EXE has no macOS-style per-app request API. Do not claim
        # authorization: the OS can still deny the actual capture operation.
        return "system_managed"
    import AVFoundation as av
    status = av.AVCaptureDevice.authorizationStatusForMediaType_(av.AVMediaTypeVideo)
    return {
        av.AVAuthorizationStatusNotDetermined: "not_determined",
        av.AVAuthorizationStatusAuthorized: "authorized",
        av.AVAuthorizationStatusDenied: "denied",
        av.AVAuthorizationStatusRestricted: "restricted",
    }.get(status, "unknown")


def camera_permission(callback):
    if sys.platform == "win32":
        callback(True)  # Attempt capture; not an assertion of OS authorization.
        return
    import AVFoundation as av
    status = av.AVCaptureDevice.authorizationStatusForMediaType_(av.AVMediaTypeVideo)
    if status == av.AVAuthorizationStatusNotDetermined:
        # PyObjC cannot create an Objective-C block from Qt's built-in emit
        # method. A real Python function is required at the native boundary.
        def completion(granted):
            callback(bool(granted))
        av.AVCaptureDevice.requestAccessForMediaType_completionHandler_(av.AVMediaTypeVideo, completion)
    else:
        callback(status == av.AVAuthorizationStatusAuthorized)


def demo_state(t):
    emotion = ("calm", "joy", "surprise", "sad")[int(t / 7) % 4]
    state = Tracking(face=(.5 + .025 * math.sin(t*.7), .32, .20), emotion=emotion, strength=.65, fps=60)
    for i, label in enumerate(("Left", "Right")):
        x = .5 + .25 * math.sin(t * .9 + i * math.pi)
        y = .61 + .16 * math.cos(t * 1.4 + i * 1.9)
        state.hands.append(Hand(label, x, y, .5+.5*math.sin(t), .5+.5*math.cos(t*.8), .7,
                                max(0, math.sin(t*2 + i)) ** 12))
    return state
