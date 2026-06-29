# pose_engine.py
# MediaPipe Tasks Pose Landmarker detection engine
# Compatible with current MediaPipe Tasks API

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Sequence

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from config import MIN_VISIBILITY
from resources import resource_path


# -------------------------------------------------------------------------
# Model configuration
# -------------------------------------------------------------------------

DEFAULT_MODEL_PATH = resource_path("models/pose_landmarker_full.task")


# -------------------------------------------------------------------------
# Pose connections
#
# The Tasks API returns landmarks but does not require mp.solutions drawing
# utilities. We draw the skeleton manually to avoid depending on the removed
# legacy mp.solutions namespace.
# -------------------------------------------------------------------------

POSE_CONNECTIONS = (
    # Face
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (9, 10),

    # Upper body
    (11, 12),
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),

    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),

    # Torso
    (11, 23),
    (12, 24),
    (23, 24),

    # Left leg
    (23, 25),
    (25, 27),
    (27, 29),
    (29, 31),
    (27, 31),

    # Right leg
    (24, 26),
    (26, 28),
    (28, 30),
    (30, 32),
    (28, 32),
)


LANDMARK_COLOR = (0, 255, 180)
CONNECTION_COLOR = (255, 200, 0)

LANDMARK_RADIUS = 4
LANDMARK_THICKNESS = -1
CONNECTION_THICKNESS = 2


def _optional_score(value: Optional[float], default: float = 1.0) -> float:
    """Convert optional MediaPipe confidence values to float."""
    if value is None:
        return default
    return float(value)


def _landmark_is_visible(landmark) -> bool:
    """
    Check visibility and presence.

    Some MediaPipe containers expose visibility/presence as optional values,
    so getattr and sensible defaults are used.
    """
    visibility = _optional_score(
        getattr(landmark, "visibility", None)
    )
    presence = _optional_score(
        getattr(landmark, "presence", None)
    )

    return (
        visibility >= MIN_VISIBILITY
        and presence >= 0.5
    )


def _normalized_to_pixel(
    landmark,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Convert normalized x/y coordinates to image pixels."""
    x = int(np.clip(landmark.x, 0.0, 1.0) * (width - 1))
    y = int(np.clip(landmark.y, 0.0, 1.0) * (height - 1))

    return x, y


def draw_pose_landmarks(
    frame: np.ndarray,
    landmarks: Sequence,
) -> None:
    """Draw pose landmarks and connections directly with OpenCV."""
    if not landmarks:
        return

    height, width = frame.shape[:2]

    # Draw connections first, so landmarks remain visible above the lines.
    for start_index, end_index in POSE_CONNECTIONS:
        if (
            start_index >= len(landmarks)
            or end_index >= len(landmarks)
        ):
            continue

        start_landmark = landmarks[start_index]
        end_landmark = landmarks[end_index]

        if not (
            _landmark_is_visible(start_landmark)
            and _landmark_is_visible(end_landmark)
        ):
            continue

        start_point = _normalized_to_pixel(
            start_landmark,
            width,
            height,
        )
        end_point = _normalized_to_pixel(
            end_landmark,
            width,
            height,
        )

        cv2.line(
            frame,
            start_point,
            end_point,
            CONNECTION_COLOR,
            CONNECTION_THICKNESS,
            cv2.LINE_AA,
        )

    # Draw landmark points.
    for landmark in landmarks:
        if not _landmark_is_visible(landmark):
            continue

        point = _normalized_to_pixel(
            landmark,
            width,
            height,
        )

        cv2.circle(
            frame,
            point,
            LANDMARK_RADIUS,
            LANDMARK_COLOR,
            LANDMARK_THICKNESS,
            cv2.LINE_AA,
        )


class PoseDetector:
    """
    Compatibility wrapper around the MediaPipe Tasks Pose Landmarker.

    VIDEO mode is used because the existing application processes webcam
    frames synchronously. It allows process_frame() to return one result for
    the current frame without rewriting main.py around asynchronous callbacks.
    """

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        num_poses: int = 1,
        min_detection_confidence: float = 0.6,
        min_presence_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
    ) -> None:
        self.model_path = Path(model_path).resolve()

        if not self.model_path.exists():
            raise FileNotFoundError(
                "Pose Landmarker model was not found:\n"
                f"{self.model_path}\n\n"
                "Download pose_landmarker_full.task and place it in:\n"
                f"{DEFAULT_MODEL_PATH.parent}"
            )

        try:
            self._model_buffer = self.model_path.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                "Pose Landmarker model could not be read:\n"
                f"{self.model_path}"
            ) from exc

        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(
                # Passing bytes avoids native-library failures on Windows
                # when the packaged app lives under a non-ASCII path.
                model_asset_buffer=self._model_buffer,
            ),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=num_poses,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False,
        )

        self._landmarker = (
            vision.PoseLandmarker.create_from_options(options)
        )

        # detect_for_video requires strictly increasing timestamps.
        self._last_timestamp_ms = -1
        self._closed = False

    def _next_timestamp_ms(self) -> int:
        """
        Return a strictly increasing monotonic timestamp in milliseconds.

        time.time() can theoretically move backwards if the system clock is
        adjusted. time.monotonic_ns() is more appropriate for video frames.
        """
        timestamp_ms = time.monotonic_ns() // 1_000_000

        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1

        self._last_timestamp_ms = timestamp_ms
        return timestamp_ms

    def process(
        self,
        frame: np.ndarray,
        timestamp_ms: int | None = None,
    ):
        if self._closed:
            raise RuntimeError(
                "PoseDetector has already been closed."
            )

        if frame is None or frame.size == 0:
            raise ValueError(
                "process() received an empty frame."
            )

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
        )

        rgb_frame = np.ascontiguousarray(rgb_frame)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame,
        )

        if timestamp_ms is None:
            timestamp_ms = self._next_timestamp_ms()
        else:
            timestamp_ms = int(timestamp_ms)

            if timestamp_ms <= self._last_timestamp_ms:
                timestamp_ms = self._last_timestamp_ms + 1

            self._last_timestamp_ms = timestamp_ms

        result = self._landmarker.detect_for_video(
            mp_image,
            timestamp_ms,
        )

        if result.pose_landmarks:
            draw_pose_landmarks(
                frame,
                result.pose_landmarks[0],
            )

        return result

    def close(self) -> None:
        """Release MediaPipe resources."""
        if not self._closed:
            self._landmarker.close()
            self._closed = True
            self._model_buffer = b""

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()


def create_pose_detector(
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> PoseDetector:
    """
    Create the new MediaPipe Tasks Pose Landmarker detector.

    This function keeps the same name used by the original main.py.
    """
    return PoseDetector(
        model_path=model_path,
        num_poses=1,
        min_detection_confidence=0.6,
        min_presence_confidence=0.6,
        min_tracking_confidence=0.6,
    )


def process_frame(
    pose: PoseDetector,
    frame: np.ndarray,
    timestamp_ms: int | None = None,
):
    return pose.process(
        frame,
        timestamp_ms=timestamp_ms,
    )


def get_landmarks(results):
    """
    Return the first person's normalized landmarks.

    The returned list contains 33 landmarks with:
    x, y, z, visibility and presence.
    """
    if results is None:
        return None

    if not results.pose_landmarks:
        return None

    return results.pose_landmarks[0]


def get_world_landmarks(results):
    """
    Return the first person's 3D world landmarks.

    World coordinates use meters, with the midpoint of the hips serving
    approximately as the coordinate origin.
    """
    if results is None:
        return None

    if not results.pose_world_landmarks:
        return None

    return results.pose_world_landmarks[0]


def open_webcam(
    cam_index: int = 0,
    width: int = 1280,
    height: int = 720,
):
    """Open webcam with the requested resolution."""
    cap = cv2.VideoCapture(cam_index)

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        width,
    )
    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        height,
    )
    cap.set(
        cv2.CAP_PROP_FPS,
        30,
    )

    if not cap.isOpened():
        cap.release()

        raise RuntimeError(
            "Cannot open webcam. Check camera permissions and make sure "
            "another application is not using the camera."
        )

    return cap
