# pose_features.py
"""
统一提取动作特征
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


# MediaPipe Pose 33个关键点索引
NOSE = 0

LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16

LEFT_HIP = 23
RIGHT_HIP = 24


def point_xyz(landmark) -> np.ndarray:
    return np.array(
        [landmark.x, landmark.y, landmark.z],
        dtype=np.float64,
    )


def distance_2d(a, b) -> float:
    return math.sqrt(
        (a.x - b.x) ** 2
        + (a.y - b.y) ** 2
    )


def calculate_angle_3d(a, b, c) -> float:
    """
    计算以b为顶点的三维夹角：
    a ---- b ---- c
    """
    ba = point_xyz(a) - point_xyz(b)
    bc = point_xyz(c) - point_xyz(b)

    denominator = np.linalg.norm(ba) * np.linalg.norm(bc)

    if denominator < 1e-8:
        return 0.0

    cosine = np.dot(ba, bc) / denominator
    cosine = np.clip(cosine, -1.0, 1.0)

    return float(np.degrees(np.arccos(cosine)))


def calculate_trunk_lean(image_landmarks) -> float:
    """
    计算躯干中心线相对垂直方向的左右倾斜角。
    主要用于正面摄像头。
    """
    left_shoulder = image_landmarks[LEFT_SHOULDER]
    right_shoulder = image_landmarks[RIGHT_SHOULDER]
    left_hip = image_landmarks[LEFT_HIP]
    right_hip = image_landmarks[RIGHT_HIP]

    shoulder_center_x = (
        left_shoulder.x + right_shoulder.x
    ) / 2.0
    shoulder_center_y = (
        left_shoulder.y + right_shoulder.y
    ) / 2.0

    hip_center_x = (
        left_hip.x + right_hip.x
    ) / 2.0
    hip_center_y = (
        left_hip.y + right_hip.y
    ) / 2.0

    dx = shoulder_center_x - hip_center_x
    dy = hip_center_y - shoulder_center_y

    return float(
        np.degrees(np.arctan2(dx, max(abs(dy), 1e-8)))
    )


def minimum_visibility(
    landmarks,
    indexes: list[int],
) -> float:
    scores = []

    for index in indexes:
        landmark = landmarks[index]
        visibility = getattr(landmark, "visibility", 1.0)

        if visibility is None:
            visibility = 1.0

        scores.append(float(visibility))

    return min(scores)


def extract_pose_features(
    image_landmarks,
    world_landmarks=None,
) -> dict[str, Any]:
    """
    标准视频和Webcam必须调用同一个函数。

    world_landmarks:
        用于关节角度。

    image_landmarks:
        用于相对高度、左右对称和躯干倾斜。
    """
    if not image_landmarks:
        raise ValueError("image_landmarks is empty")

    # 世界坐标不可用时退回图像归一化坐标
    angle_landmarks = (
        world_landmarks
        if world_landmarks
        else image_landmarks
    )

    left_elbow_angle = calculate_angle_3d(
        angle_landmarks[LEFT_SHOULDER],
        angle_landmarks[LEFT_ELBOW],
        angle_landmarks[LEFT_WRIST],
    )

    right_elbow_angle = calculate_angle_3d(
        angle_landmarks[RIGHT_SHOULDER],
        angle_landmarks[RIGHT_ELBOW],
        angle_landmarks[RIGHT_WRIST],
    )

    # 髋部—肩部—肘部夹角
    # 手臂自然下垂时接近0°
    # 手臂向上伸直时接近180°
    left_shoulder_angle = calculate_angle_3d(
        angle_landmarks[LEFT_HIP],
        angle_landmarks[LEFT_SHOULDER],
        angle_landmarks[LEFT_ELBOW],
    )

    right_shoulder_angle = calculate_angle_3d(
        angle_landmarks[RIGHT_HIP],
        angle_landmarks[RIGHT_SHOULDER],
        angle_landmarks[RIGHT_ELBOW],
    )

    left_shoulder = image_landmarks[LEFT_SHOULDER]
    right_shoulder = image_landmarks[RIGHT_SHOULDER]
    left_wrist = image_landmarks[LEFT_WRIST]
    right_wrist = image_landmarks[RIGHT_WRIST]
    left_hip = image_landmarks[LEFT_HIP]
    right_hip = image_landmarks[RIGHT_HIP]

    shoulder_center = SimplePoint(
        x=(left_shoulder.x + right_shoulder.x) / 2.0,
        y=(left_shoulder.y + right_shoulder.y) / 2.0,
    )

    hip_center = SimplePoint(
        x=(left_hip.x + right_hip.x) / 2.0,
        y=(left_hip.y + right_hip.y) / 2.0,
    )

    torso_length = max(
        distance_2d(shoulder_center, hip_center),
        1e-6,
    )

    # 图像坐标y向下，所以 shoulder.y - wrist.y 为正表示手腕更高
    left_wrist_height = (
        left_shoulder.y - left_wrist.y
    ) / torso_length

    right_wrist_height = (
        right_shoulder.y - right_wrist.y
    ) / torso_length

    wrist_asymmetry = abs(
        left_wrist.y - right_wrist.y
    ) / torso_length

    shoulder_asymmetry = abs(
        left_shoulder.y - right_shoulder.y
    ) / torso_length

    required_indexes = [
        LEFT_SHOULDER,
        RIGHT_SHOULDER,
        LEFT_ELBOW,
        RIGHT_ELBOW,
        LEFT_WRIST,
        RIGHT_WRIST,
        LEFT_HIP,
        RIGHT_HIP,
    ]

    return {
        "left_elbow_angle": left_elbow_angle,
        "right_elbow_angle": right_elbow_angle,
        "left_shoulder_angle": left_shoulder_angle,
        "right_shoulder_angle": right_shoulder_angle,
        "left_wrist_height": left_wrist_height,
        "right_wrist_height": right_wrist_height,
        "wrist_asymmetry": wrist_asymmetry,
        "shoulder_asymmetry": shoulder_asymmetry,
        "trunk_lean_angle": calculate_trunk_lean(
            image_landmarks
        ),
        "minimum_visibility": minimum_visibility(
            image_landmarks,
            required_indexes,
        ),
    }


class SimplePoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y