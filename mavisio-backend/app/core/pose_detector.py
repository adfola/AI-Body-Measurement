"""
PoseDetector — unified body detection pipeline.

Architecture
------------
    1. MediaPipe Pose (primary): provides stable 33 world landmarks
       including the key anatomical joints for tailoring measurements.
    2. YOLO Segmentation: always run in parallel to get the person
       silhouette mask, which is used for contour-based width extraction.
    3. Custom YOLO keypoints: optional add-on for tailor-specific points
       that MediaPipe does not provide (loaded only if weights exist).
    4. YOLO Pose fallback: if MediaPipe fails to detect a person,
       fall back to YOLO pose estimation (returns fewer joints, lower
       confidence — but better than nothing).

The LandmarkTracker (Kalman-based smoother) is NOT run here; it lives in
the WebSocket session context (MeasurementContext) so that per-session
state is maintained correctly.
"""
from __future__ import annotations

from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from app.vision.yolo_detector import YoloSegmentor, CustomKeypointDetector

# ---------------------------------------------------------------------------
# MediaPipe landmark index → name mapping (subset used for tailoring)
# ---------------------------------------------------------------------------
NAMES: dict[str, int] = {
    "nose": 0,
    "l_shoulder": 11, "r_shoulder": 12,
    "l_elbow": 13,    "r_elbow": 14,
    "l_wrist": 15,    "r_wrist": 16,
    "l_hip": 23,      "r_hip": 24,
    "l_knee": 25,     "r_knee": 26,
    "l_ankle": 27,    "r_ankle": 28,
    "l_heel": 29,     "r_heel": 30,
}


class PoseDetector:
    """
    Unified detector: MediaPipe Pose + YOLO segmentation + custom keypoints.

    Parameters
    ----------
    model_complexity : int
        MediaPipe Pose model complexity (0 = fastest, 2 = most accurate).
    yolo_weights : str
        YOLO pose weights for fallback detection.
    yolo_seg_weights : str
        YOLO segmentation weights for body mask extraction.
    custom_kp_weights : str | None
        Path to custom tailor-keypoint YOLO model (optional).
    min_detection_confidence : float
    min_tracking_confidence : float
    """

    def __init__(
        self,
        model_complexity: int = 1,
        yolo_weights: str = "yolo11n-pose.pt",
        yolo_seg_weights: str = "yolo11n-seg.pt",
        custom_kp_weights: str | None = None,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        # Primary: MediaPipe Pose
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            enable_segmentation=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        # Secondary: YOLO (segmentation + fallback pose)
        self.yolo_segmentor = YoloSegmentor(
            seg_weights=yolo_seg_weights,
            pose_weights=yolo_weights,
        )

        # Optional: Custom tailor keypoints
        self.custom_detector = CustomKeypointDetector(weights_path=custom_kp_weights)

        self._yolo_loaded = False

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> dict[str, Any] | None:
        """
        Process one BGR frame and return a structured result dict.

        Returns
        -------
        dict with keys:
            source       : "mediapipe" | "yolo_fallback"
            px           : {name: (x_px, y_px, visibility)}  image coords
            world        : {name: (x, y, z)}  world coords (metres, MediaPipe)
            mask         : H×W float32 segmentation mask (best available)
            conf         : {name: float}  per-landmark confidence
            frame_conf   : float  mean frame confidence
            custom_kp    : {name: (x_px, y_px, conf)}  tailor-specific points
        or None if no person is detected by any method.
        """
        height, width = frame.shape[:2]

        # ------ Step 1: MediaPipe Pose ------
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_result = self.pose.process(rgb)

        mp_ok = (
            mp_result.pose_landmarks is not None
            and mp_result.pose_world_landmarks is not None
        )

        # ------ Step 2: YOLO Segmentation (always run for mask) ------
        seg = self.yolo_segmentor.segment_person(frame)

        # ------ Step 3: Build landmark dict ------
        if mp_ok:
            lm = mp_result.pose_landmarks.landmark
            wlm = mp_result.pose_world_landmarks.landmark

            px: dict[str, tuple[float, float, float]] = {
                name: (lm[idx].x * width, lm[idx].y * height, float(getattr(lm[idx], "visibility", 0.5)))
                for name, idx in NAMES.items()
            }
            world: dict[str, tuple[float, float, float]] = {
                name: (wlm[idx].x, wlm[idx].y, wlm[idx].z)
                for name, idx in NAMES.items()
            }
            conf: dict[str, float] = {
                name: float(getattr(lm[idx], "visibility", 0.5))
                for name, idx in NAMES.items()
            }
            frame_conf = float(sum(conf.values()) / max(len(conf), 1))

            # Best mask: prefer YOLO (sharper silhouette) over MediaPipe soft mask
            best_mask = (
                seg.mask
                if seg.mask is not None
                else (mp_result.segmentation_mask if mp_result.segmentation_mask is not None else None)
            )

            # ------ Step 4: Custom keypoints ------
            custom_kp = self.custom_detector.detect(frame, px)

            return {
                "source": "mediapipe",
                "px": px,
                "world": world,
                "mask": best_mask,
                "conf": conf,
                "frame_conf": frame_conf,
                "custom_kp": custom_kp.points,
                "seg_confidence": seg.confidence,
            }

        # ------ Fallback: YOLO Pose ------
        fallback = self.yolo_segmentor.fallback_pose(frame)
        px_fallback = self.yolo_segmentor.coco_to_mediapipe_format(fallback)

        if px_fallback is None:
            return None  # No person detected by any method

        # Build a minimal world dict from COCO (no real 3D — zero z)
        world_fallback: dict[str, tuple[float, float, float]] = {
            name: (x / width, y / height, 0.0)
            for name, (x, y, conf_v) in px_fallback.items()
            if name in NAMES
        }
        conf_fallback = {
            name: conf_v
            for name, (_, _, conf_v) in px_fallback.items()
            if name in NAMES
        }
        frame_conf_fb = float(
            sum(conf_fallback.values()) / max(len(conf_fallback), 1)
        )

        # Filter to only known NAMES for compatibility
        px_filtered = {
            name: (x, y, c)
            for name, (x, y, c) in px_fallback.items()
            if name in NAMES
        }
        world_filtered = {name: v for name, v in world_fallback.items() if name in NAMES}

        return {
            "source": "yolo_fallback",
            "px": px_filtered,
            "world": world_filtered,
            "mask": seg.mask,
            "conf": conf_fallback,
            "frame_conf": frame_conf_fb,
            "custom_kp": {},
            "seg_confidence": seg.confidence,
        }

    def close(self) -> None:
        self.pose.close()
