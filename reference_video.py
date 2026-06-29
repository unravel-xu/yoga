from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from pose_engine import (
    create_pose_detector,
    get_landmarks,
    get_world_landmarks,
    process_frame,
)
from pose_features import extract_pose_features
from utils import draw_rounded_rect
from config import COLOR_GREEN, COLOR_ORANGE, COLOR_WHITE, COLOR_YELLOW


@dataclass
class ReferenceFrame:
    frame: np.ndarray | None
    features: dict[str, float] | None
    pose_detected: bool
    position_seconds: float
    duration_seconds: float
    paused: bool


class ReferenceVideoGuide:
    """Looping reference video reader with pose-feature extraction."""

    def __init__(
        self,
        video_path: str | Path,
        *,
        mirror: bool = True,
        processing_width: int = 640,
    ) -> None:
        self.video_path = Path(video_path)
        self.mirror = mirror
        self.processing_width = processing_width
        self.paused = False

        if not self.video_path.exists():
            raise FileNotFoundError(
                f"Reference video not found: {self.video_path}"
            )

        self.cap = cv2.VideoCapture(str(self.video_path))

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Cannot open reference video: {self.video_path}"
            )

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.frame_count = int(
            self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        )
        self.duration_seconds = (
            self.frame_count / self.fps
            if self.frame_count > 0 and self.fps > 0
            else 0.0
        )

        self.detector = create_pose_detector()
        self.last_frame: np.ndarray | None = None
        self.last_features: dict[str, float] | None = None
        self.last_pose_detected = False
        self.last_position_seconds = 0.0

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def reset(self) -> None:
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.last_frame = None
        self.last_features = None
        self.last_pose_detected = False
        self.last_position_seconds = 0.0

    def read(self) -> ReferenceFrame:
        if self.paused and self.last_frame is not None:
            return self._current_state()

        success, frame = self.cap.read()

        if not success or frame is None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            success, frame = self.cap.read()

        if not success or frame is None:
            return ReferenceFrame(
                frame=self.last_frame,
                features=self.last_features,
                pose_detected=False,
                position_seconds=self.last_position_seconds,
                duration_seconds=self.duration_seconds,
                paused=self.paused,
            )

        if self.mirror:
            frame = cv2.flip(frame, 1)

        frame = self._resize_for_processing(frame)
        frame_index = max(
            int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1,
            0,
        )
        timestamp_ms = int(frame_index / self.fps * 1000)

        result = process_frame(
            self.detector,
            frame,
            timestamp_ms=timestamp_ms,
        )

        landmarks = get_landmarks(result)
        world_landmarks = get_world_landmarks(result)
        pose_detected = landmarks is not None

        if landmarks:
            self.last_features = extract_pose_features(
                landmarks,
                world_landmarks,
            )

        self.last_frame = frame
        self.last_pose_detected = pose_detected
        self.last_position_seconds = (
            frame_index / self.fps
            if self.fps > 0
            else 0.0
        )

        return self._current_state()

    def close(self) -> None:
        self.detector.close()
        self.cap.release()

    def _resize_for_processing(
        self,
        frame: np.ndarray,
    ) -> np.ndarray:
        height, width = frame.shape[:2]

        if width <= self.processing_width:
            return frame

        scale = self.processing_width / width
        new_size = (
            self.processing_width,
            max(1, int(height * scale)),
        )

        return cv2.resize(
            frame,
            new_size,
            interpolation=cv2.INTER_AREA,
        )

    def _current_state(self) -> ReferenceFrame:
        return ReferenceFrame(
            frame=self.last_frame,
            features=self.last_features,
            pose_detected=self.last_pose_detected,
            position_seconds=self.last_position_seconds,
            duration_seconds=self.duration_seconds,
            paused=self.paused,
        )


def draw_reference_overlay(
    frame: np.ndarray,
    reference: ReferenceFrame | None,
    *,
    x: int = 20,
    y: int = 75,
    width: int = 320,
) -> None:
    """Draw the reference video as a small picture-in-picture panel."""
    frame_h, frame_w = frame.shape[:2]
    available_width = frame_w - x - 330

    if available_width < 140:
        available_width = frame_w - x * 2

    panel_w = max(
        140,
        min(width, available_width),
    )
    panel_h = int(panel_w * 9 / 16)

    if y + panel_h + 34 > frame_h:
        y = max(65, frame_h - panel_h - 44)

    draw_rounded_rect(
        frame,
        x - 6,
        y - 26,
        panel_w + 12,
        panel_h + 34,
        6,
        (20, 20, 20),
        alpha=0.62,
    )

    cv2.putText(
        frame,
        _format_reference_title(reference),
        (x, y - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        COLOR_YELLOW,
        1,
        cv2.LINE_AA,
    )

    canvas = np.zeros(
        (panel_h, panel_w, 3),
        dtype=np.uint8,
    )

    if reference and reference.frame is not None:
        fitted = _fit_frame(
            reference.frame,
            panel_w,
            panel_h,
        )
        canvas[:, :] = fitted
    else:
        cv2.putText(
            canvas,
            "No reference",
            (18, panel_h // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            COLOR_WHITE,
            1,
            cv2.LINE_AA,
        )

    frame[y:y + panel_h, x:x + panel_w] = canvas

    border_color = (
        COLOR_GREEN
        if reference and reference.pose_detected
        else COLOR_ORANGE
    )

    cv2.rectangle(
        frame,
        (x, y),
        (x + panel_w, y + panel_h),
        border_color,
        2,
        cv2.LINE_AA,
    )


def _fit_frame(
    image: np.ndarray,
    box_w: int,
    box_h: int,
) -> np.ndarray:
    image_h, image_w = image.shape[:2]
    scale = min(
        box_w / max(image_w, 1),
        box_h / max(image_h, 1),
    )
    resized_w = max(1, int(image_w * scale))
    resized_h = max(1, int(image_h * scale))

    resized = cv2.resize(
        image,
        (resized_w, resized_h),
        interpolation=cv2.INTER_AREA,
    )
    canvas = np.zeros(
        (box_h, box_w, 3),
        dtype=np.uint8,
    )
    x_offset = (box_w - resized_w) // 2
    y_offset = (box_h - resized_h) // 2
    canvas[
        y_offset:y_offset + resized_h,
        x_offset:x_offset + resized_w,
    ] = resized

    return canvas


def _format_reference_title(
    reference: ReferenceFrame | None,
) -> str:
    if not reference:
        return "Reference"

    duration = max(reference.duration_seconds, 0.0)
    current = max(reference.position_seconds, 0.0)
    state = "PAUSED" if reference.paused else "PLAY"

    if duration <= 0:
        return f"Reference  {state}"

    return (
        f"Reference  {state}  "
        f"{current:04.1f}/{duration:04.1f}s"
    )
