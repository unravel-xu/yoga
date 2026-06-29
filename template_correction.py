# template_correction.py

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PoseError:
    code: str
    message: str
    value: float
    target: float
    severity: float


@dataclass
class PoseEvaluation:
    is_correct: bool
    checks: dict[str, bool]
    errors: list[PoseError]
    primary_feedback: str
    score: float


REFERENCE_MATCH_TOLERANCES = {
    "left_elbow_angle": 16.0,
    "right_elbow_angle": 16.0,
    "left_shoulder_angle": 18.0,
    "right_shoulder_angle": 18.0,
    "left_wrist_height": 0.20,
    "right_wrist_height": 0.20,
    "wrist_asymmetry": 0.16,
    "trunk_lean_angle": 12.0,
}


def load_template(
    path: str | Path,
) -> dict[str, Any]:
    with Path(path).open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def normalized_error(
    value: float,
    target: float,
    tolerance: float,
) -> float:
    if tolerance <= 0:
        return 0.0

    return abs(value - target) / tolerance


def evaluate_pose(
    current: dict[str, float],
    template: dict[str, Any],
) -> PoseEvaluation:
    target_features = template["features"]

    checks: dict[str, bool] = {}
    errors: list[PoseError] = []

    def check_minimum(
        feature_name: str,
        code: str,
        message: str,
    ):
        specification = target_features[feature_name]

        target = float(specification["target"])
        tolerance = float(specification["tolerance"])
        minimum = target - tolerance
        value = float(current[feature_name])

        passed = value >= minimum
        checks[feature_name] = passed

        if not passed:
            severity = (
                minimum - value
            ) / max(tolerance, 1e-6)

            errors.append(
                PoseError(
                    code=code,
                    message=message,
                    value=value,
                    target=minimum,
                    severity=severity,
                )
            )

    def check_maximum(
        feature_name: str,
        maximum: float,
        code: str,
        message: str,
    ):
        value = abs(float(current[feature_name]))
        passed = value <= maximum
        checks[feature_name] = passed

        if not passed:
            severity = (
                value - maximum
            ) / max(maximum, 1e-6)

            errors.append(
                PoseError(
                    code=code,
                    message=message,
                    value=value,
                    target=maximum,
                    severity=severity,
                )
            )

    # 双臂是否抬到标准范围
    check_minimum(
        "left_shoulder_angle",
        "left_arm_low",
        "Raise your left arm a little higher.",
    )

    check_minimum(
        "right_shoulder_angle",
        "right_arm_low",
        "Raise your right arm a little higher.",
    )

    # 肘部是否充分伸展
    check_minimum(
        "left_elbow_angle",
        "left_elbow_bent",
        "Straighten your left elbow gently.",
    )

    check_minimum(
        "right_elbow_angle",
        "right_elbow_bent",
        "Straighten your right elbow gently.",
    )

    # 对称性和躯干倾斜不建议仅使用模板差值，
    # 使用更容易解释的固定上限
    check_maximum(
        "wrist_asymmetry",
        maximum=0.16,
        code="arms_asymmetric",
        message="Keep both hands at a similar height.",
    )

    check_maximum(
        "trunk_lean_angle",
        maximum=12.0,
        code="trunk_lean",
        message="Bring your body gently back to center.",
    )

    # 按严重程度选择最主要问题
    errors.sort(
        key=lambda item: item.severity,
        reverse=True,
    )

    if errors:
        primary_feedback = errors[0].message
    else:
        primary_feedback = "Great posture. Keep holding."

    total_severity = sum(
        min(error.severity, 2.0)
        for error in errors
    )

    score = max(
        0.0,
        100.0 - total_severity * 20.0,
    )

    return PoseEvaluation(
        is_correct=len(errors) == 0,
        checks=checks,
        errors=errors,
        primary_feedback=primary_feedback,
        score=score,
    )


def evaluate_against_reference(
    current: dict[str, float],
    reference: dict[str, float] | None,
    tolerances: dict[str, float] | None = None,
) -> PoseEvaluation:
    """
    Compare the live user pose against the current reference-video pose.

    This is intentionally feature-based instead of pixel-based, so camera
    distance and body size have much less influence on the feedback.
    """
    if not reference:
        return PoseEvaluation(
            is_correct=False,
            checks={"reference_pose": False},
            errors=[],
            primary_feedback="Reference pose is not ready.",
            score=0.0,
        )

    tolerances = {
        **REFERENCE_MATCH_TOLERANCES,
        **(tolerances or {}),
    }

    checks: dict[str, bool] = {}
    errors: list[PoseError] = []

    def add_feature_check(
        feature_name: str,
        low_code: str,
        low_message: str,
        high_code: str,
        high_message: str,
    ) -> None:
        if feature_name not in current or feature_name not in reference:
            checks[feature_name] = False
            return

        value = float(current[feature_name])
        target = float(reference[feature_name])
        tolerance = float(tolerances[feature_name])
        difference = value - target
        passed = abs(difference) <= tolerance
        checks[feature_name] = passed

        if passed:
            return

        severity = abs(difference) / max(tolerance, 1e-6)
        code = low_code if difference < 0 else high_code
        message = low_message if difference < 0 else high_message

        errors.append(
            PoseError(
                code=code,
                message=message,
                value=value,
                target=target,
                severity=severity,
            )
        )

    def add_upper_bound_check(
        feature_name: str,
        code: str,
        message: str,
    ) -> None:
        if feature_name not in current or feature_name not in reference:
            checks[feature_name] = False
            return

        value = abs(float(current[feature_name]))
        target = abs(float(reference[feature_name]))
        tolerance = float(tolerances[feature_name])
        maximum = target + tolerance
        passed = value <= maximum
        checks[feature_name] = passed

        if passed:
            return

        errors.append(
            PoseError(
                code=code,
                message=message,
                value=value,
                target=maximum,
                severity=(value - maximum) / max(tolerance, 1e-6),
            )
        )

    add_feature_check(
        "left_shoulder_angle",
        "left_arm_low",
        "Raise your left arm to match the video.",
        "left_arm_high",
        "Lower your left arm slightly.",
    )
    add_feature_check(
        "right_shoulder_angle",
        "right_arm_low",
        "Raise your right arm to match the video.",
        "right_arm_high",
        "Lower your right arm slightly.",
    )
    add_feature_check(
        "left_elbow_angle",
        "left_elbow_bent",
        "Straighten your left elbow a little.",
        "left_elbow_too_straight",
        "Bend your left elbow to follow the video.",
    )
    add_feature_check(
        "right_elbow_angle",
        "right_elbow_bent",
        "Straighten your right elbow a little.",
        "right_elbow_too_straight",
        "Bend your right elbow to follow the video.",
    )
    add_feature_check(
        "left_wrist_height",
        "left_hand_low",
        "Lift your left hand higher.",
        "left_hand_high",
        "Lower your left hand slightly.",
    )
    add_feature_check(
        "right_wrist_height",
        "right_hand_low",
        "Lift your right hand higher.",
        "right_hand_high",
        "Lower your right hand slightly.",
    )
    add_upper_bound_check(
        "wrist_asymmetry",
        code="hands_not_level",
        message="Keep both hands at a similar height.",
    )
    add_feature_check(
        "trunk_lean_angle",
        "trunk_tilt",
        "Match the body tilt in the reference video.",
        "trunk_tilt",
        "Match the body tilt in the reference video.",
    )

    visibility = float(current.get("minimum_visibility", 1.0))
    checks["minimum_visibility"] = visibility >= 0.50

    if not checks["minimum_visibility"]:
        errors.append(
            PoseError(
                code="low_visibility",
                message="Move fully into the camera frame.",
                value=visibility,
                target=0.50,
                severity=(0.50 - visibility) / 0.50,
            )
        )

    errors.sort(
        key=lambda item: item.severity,
        reverse=True,
    )

    primary_feedback = (
        errors[0].message
        if errors
        else "Great match. Keep following the video."
    )
    total_severity = sum(
        min(error.severity, 2.0)
        for error in errors
    )
    score = max(
        0.0,
        100.0 - total_severity * 8.0,
    )

    return PoseEvaluation(
        is_correct=len(errors) == 0,
        checks=checks,
        errors=errors,
        primary_feedback=primary_feedback,
        score=score,
    )
