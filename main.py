# main.py - Yoga reference-video pose correction
# Run with: python3.11 main.py

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from config import *
from pose_engine import (
    create_pose_detector,
    get_landmarks,
    get_world_landmarks,
    open_webcam,
    process_frame,
)
from pose_features import extract_pose_features
from reference_video import (
    ReferenceVideoGuide,
    draw_reference_overlay,
)
from resources import resource_path
from template_correction import (
    PoseEvaluation,
    evaluate_against_reference,
)
from utils import (
    FPSCounter,
    calculate_angle,
    draw_angle_label,
    draw_coordinates,
    draw_feedback_banner,
    draw_status_panel,
)


DEFAULT_REFERENCE_VIDEO = resource_path("videos/daily_yoga.mp4")

MATCH_LABELS = [
    "1. Left arm match",
    "2. Right arm match",
    "3. Elbows match",
    "4. Hands aligned",
    "5. Torso centered",
    "6. Body visible",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mirror a reference yoga video and correct live posture.",
    )
    parser.add_argument(
        "--reference-video",
        default=str(DEFAULT_REFERENCE_VIDEO),
        help="Path to the demonstration video shown in the small window.",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Requested webcam width.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Requested webcam height.",
    )
    parser.add_argument(
        "--no-mirror-reference",
        action="store_true",
        help="Do not horizontally mirror the reference video.",
    )

    return parser.parse_args()


def build_match_checks(
    evaluation: PoseEvaluation | None,
    *,
    user_visible: bool,
    reference_visible: bool,
) -> list[bool]:
    if evaluation is None:
        return [False] * len(MATCH_LABELS)

    checks = evaluation.checks

    return [
        checks.get("left_shoulder_angle", False)
        and checks.get("left_wrist_height", False),
        checks.get("right_shoulder_angle", False)
        and checks.get("right_wrist_height", False),
        checks.get("left_elbow_angle", False)
        and checks.get("right_elbow_angle", False),
        checks.get("wrist_asymmetry", False),
        checks.get("trunk_lean_angle", False),
        user_visible
        and reference_visible
        and checks.get("minimum_visibility", False),
    ]


def draw_user_angles(
    frame,
    landmarks,
) -> None:
    h, w = frame.shape[:2]
    left_angle = calculate_angle(
        landmarks[LANDMARKS["LEFT_SHOULDER"]],
        landmarks[LANDMARKS["LEFT_ELBOW"]],
        landmarks[LANDMARKS["LEFT_WRIST"]],
    )
    right_angle = calculate_angle(
        landmarks[LANDMARKS["RIGHT_SHOULDER"]],
        landmarks[LANDMARKS["RIGHT_ELBOW"]],
        landmarks[LANDMARKS["RIGHT_WRIST"]],
    )

    draw_angle_label(
        frame,
        landmarks[LANDMARKS["LEFT_ELBOW"]],
        left_angle,
        w,
        h,
    )
    draw_angle_label(
        frame,
        landmarks[LANDMARKS["RIGHT_ELBOW"]],
        right_angle,
        w,
        h,
    )


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("  Yoga Reference-Video Pose Correction")
    print("=" * 60)
    print(f"Reference video: {args.reference_video}")
    print("Controls: Q = quit | Space = pause/play reference | R = restart")
    print()

    cap = None
    user_detector = None
    reference_guide = None
    fps_counter = FPSCounter()
    last_log_time = 0.0

    try:
        cap = open_webcam(
            cam_index=args.camera_index,
            width=args.width,
            height=args.height,
        )
        user_detector = create_pose_detector()
        reference_guide = ReferenceVideoGuide(
            args.reference_video,
            mirror=not args.no_mirror_reference,
        )

        while cap.isOpened():
            reference = reference_guide.read()
            success, frame = cap.read()

            if not success or frame is None:
                continue

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            fps = fps_counter.update()

            results = process_frame(
                user_detector,
                frame,
            )
            landmarks = get_landmarks(results)
            world_landmarks = get_world_landmarks(results)
            user_visible = landmarks is not None
            evaluation = None
            match_score = 0.0
            banner_message = "Stand in front of camera"
            banner_color = COLOR_YELLOW

            if landmarks:
                features = extract_pose_features(
                    landmarks,
                    world_landmarks,
                )

                evaluation = evaluate_against_reference(
                    features,
                    reference.features,
                )
                match_score = evaluation.score
                banner_message = evaluation.primary_feedback

                if not reference.features:
                    banner_color = COLOR_YELLOW
                elif not reference.pose_detected:
                    banner_message = "Waiting for a clear reference pose."
                    banner_color = COLOR_YELLOW
                elif evaluation.is_correct:
                    banner_color = COLOR_GREEN
                elif evaluation.score >= 65:
                    banner_color = COLOR_YELLOW
                else:
                    banner_color = COLOR_RED

                draw_user_angles(
                    frame,
                    landmarks,
                )
                draw_coordinates(
                    frame,
                    landmarks,
                    w,
                    h,
                )

                now = time.time()

                if now - last_log_time >= 1.0:
                    last_log_time = now
                    print(
                        f"[FPS:{fps:.1f}] "
                        f"Score:{match_score:.0f} "
                        f"Feedback:{banner_message}"
                    )

            checks = build_match_checks(
                evaluation,
                user_visible=user_visible,
                reference_visible=reference.pose_detected,
            )

            draw_status_panel(
                frame,
                checks,
                hold_timer=0.0,
                rest_timer=0.0,
                phase="FOLLOW VIDEO",
                fps=fps,
                labels=MATCH_LABELS,
                score=match_score,
            )
            draw_reference_overlay(
                frame,
                reference,
            )
            draw_feedback_banner(
                frame,
                banner_message,
                banner_color,
            )
            cv2.putText(
                frame,
                f"Reference: {Path(args.reference_video).name}",
                (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                COLOR_WHITE,
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(
                "Yoga Pose Correction - Reference Video",
                frame,
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord(" "):
                reference_guide.toggle_pause()
                continue

            if key == ord("r"):
                reference_guide.reset()
                print("Reference video restarted.")

    finally:
        if reference_guide is not None:
            reference_guide.close()

        if user_detector is not None:
            user_detector.close()

        if cap is not None:
            cap.release()

        cv2.destroyAllWindows()
        print("\nSession ended.")


if __name__ == "__main__":
    main()
