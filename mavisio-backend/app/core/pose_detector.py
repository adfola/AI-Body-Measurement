from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from ultralytics import YOLO

NAMES = {
    "nose": 0, "l_shoulder": 11, "r_shoulder": 12, "l_elbow": 13,
    "r_elbow": 14, "l_wrist": 15, "r_wrist": 16, "l_hip": 23,
    "r_hip": 24, "l_knee": 25, "r_knee": 26, "l_ankle": 27,
    "r_ankle": 28, "l_heel": 29, "r_heel": 30,
}


class PoseDetector:
    def __init__(self, model_complexity: int = 1, yolo_weights: str = "yolo11n-pose.pt"):
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            enable_segmentation=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.yolo_weights = yolo_weights
        self.yolo: YOLO | None = None

    def process_frame(self, frame: np.ndarray) -> dict[str, Any] | None:
        height, width = frame.shape[:2]
        result = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if result.pose_landmarks and result.pose_world_landmarks and result.segmentation_mask is not None:
            landmarks = result.pose_landmarks.landmark
            world_landmarks = result.pose_world_landmarks.landmark
            return {
                "source": "mediapipe",
                "px": {
                    name: (landmarks[index].x * width, landmarks[index].y * height, landmarks[index].visibility)
                    for name, index in NAMES.items()
                },
                "world": {
                    name: (world_landmarks[index].x, world_landmarks[index].y, world_landmarks[index].z)
                    for name, index in NAMES.items()
                },
                "mask": result.segmentation_mask,
            }
        if self.yolo is None:
            self.yolo = YOLO(self.yolo_weights)
        detection = self.yolo(frame, verbose=False)[0]
        if detection.keypoints is not None and len(detection.keypoints.xy):
            return {"source": "yolo", "px": None, "world": None, "mask": None}
        return None

    def close(self) -> None:
        self.pose.close()
