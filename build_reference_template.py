# build_reference_template.py

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from pose_engine import (
    create_pose_detector,
    process_frame,
    get_landmarks,
    get_world_landmarks,
)
from pose_features import extract_pose_features


VIDEO_PATH = Path(
    "./videos/daily_yoga.mp4"
)

OUTPUT_PATH = Path(
    "templates/urdhva_hastasana.json"
)

# 手动指定标准视频中“稳定保持”的时间段
HOLD_START_SECONDS = 50.0
HOLD_END_SECONDS = 56.0

MIN_VISIBILITY = 0.60


TOLERANCES = {
    "left_elbow_angle": 15.0,
    "right_elbow_angle": 15.0,
    "left_shoulder_angle": 18.0,
    "right_shoulder_angle": 18.0,
    "left_wrist_height": 0.18,
    "right_wrist_height": 0.18,
    "wrist_asymmetry": 0.10,
    "trunk_lean_angle": 8.0,
}


def robust_median(values: list[float]) -> float:
    return float(np.median(np.asarray(values)))


def percentile(
    values: list[float],
    q: float,
) -> float:
    return float(
        np.percentile(np.asarray(values), q)
    )


def main():
    if not VIDEO_PATH.exists():
        raise FileNotFoundError(
            f"Reference video not found: {VIDEO_PATH}"
        )

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open video: {VIDEO_PATH}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        raise RuntimeError(
            "Cannot read video FPS."
        )

    frame_count = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    print(f"FPS: {fps:.2f}")
    print(f"Frames: {frame_count}")
    print(
        "Hold segment:",
        HOLD_START_SECONDS,
        "to",
        HOLD_END_SECONDS,
        "seconds",
    )

    collected: dict[str, list[float]] = {}

    detector = create_pose_detector()

    frame_index = 0
    accepted_frames = 0

    try:
        while True:
            success, frame = cap.read()

            if not success:
                break

            timestamp_ms = int(
                frame_index / fps * 1000
            )

            current_seconds = frame_index / fps
            frame_index += 1

            if current_seconds < HOLD_START_SECONDS:
                continue

            if current_seconds > HOLD_END_SECONDS:
                break

            result = process_frame(
                detector,
                frame,
                timestamp_ms=timestamp_ms,
            )

            image_landmarks = get_landmarks(result)
            world_landmarks = get_world_landmarks(result)

            if not image_landmarks:
                continue

            features = extract_pose_features(
                image_landmarks,
                world_landmarks,
            )

            if (
                features["minimum_visibility"]
                < MIN_VISIBILITY
            ):
                continue

            accepted_frames += 1

            for name, value in features.items():
                if name == "minimum_visibility":
                    continue

                collected.setdefault(name, []).append(
                    float(value)
                )

    finally:
        detector.close()
        cap.release()

    if accepted_frames < 10:
        raise RuntimeError(
            "Too few valid frames. Check hold segment, "
            "visibility or reference video."
        )

    template_features = {}

    for name, values in collected.items():
        median = robust_median(values)
        p10 = percentile(values, 10)
        p90 = percentile(values, 90)
        tolerance = TOLERANCES.get(name, 0.0)

        template_features[name] = {
            "target": median,
            "observed_p10": p10,
            "observed_p90": p90,
            "tolerance": tolerance,
        }

    template = {
        "action_id": "urdhva_hastasana",
        "display_name": "Raised Hands Pose",
        "reference_video": str(VIDEO_PATH),
        "hold_start_seconds": HOLD_START_SECONDS,
        "hold_end_seconds": HOLD_END_SECONDS,
        "accepted_frames": accepted_frames,
        "features": template_features,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            template,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(f"Accepted frames: {accepted_frames}")
    print(f"Template saved to: {OUTPUT_PATH}")

    for name, values in template_features.items():
        print(
            f"{name:25s}",
            f"target={values['target']:.3f}",
            f"tolerance={values['tolerance']:.3f}",
        )


if __name__ == "__main__":
    main()