"""
Landmark tracker: wraps the per-landmark Kalman filter and exposes a
confidence-gated update interface used by the vision pipeline.

Pipeline position
-----------------
    Raw detector output (MediaPipe / YOLO)
        ↓
    LandmarkTracker.update(landmarks, confidences)
        ↓  (confidence check + Kalman smoothing)
    stable landmarks dict
        ↓
    TailoringEngine / circumference engine
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.core.kalman_filter import LandmarkKalmanFilter2D

# Canonical MediaPipe Pose landmark indices used in this project
LANDMARK_NAMES = [
    "nose",
    "l_shoulder", "r_shoulder",
    "l_elbow", "r_elbow",
    "l_wrist", "r_wrist",
    "l_hip", "r_hip",
    "l_knee", "r_knee",
    "l_ankle", "r_ankle",
    "l_heel", "r_heel",
]

# MediaPipe index → name lookup
MP_INDEX_MAP: dict[int, str] = {
    0: "nose",
    11: "l_shoulder", 12: "r_shoulder",
    13: "l_elbow",    14: "r_elbow",
    15: "l_wrist",    16: "r_wrist",
    23: "l_hip",      24: "r_hip",
    25: "l_knee",     26: "r_knee",
    27: "l_ankle",    28: "r_ankle",
    29: "l_heel",     30: "r_heel",
}

N_LANDMARKS = len(LANDMARK_NAMES)
_NAME_TO_IDX = {name: idx for idx, name in enumerate(LANDMARK_NAMES)}


class LandmarkTracker:
    """
    Tracks body landmarks across frames with:
    - Per-landmark confidence gating
    - Kalman position + velocity smoothing
    - Frame-level confidence scoring

    Parameters
    ----------
    min_confidence : float
        Per-landmark confidence threshold below which the landmark position
        is predicted (not updated).  Matches LandmarkKalmanFilter2D behaviour.
    min_frame_confidence : float
        Minimum *frame-level* confidence required to accept any measurement
        from this frame.  Frame confidence = mean of all landmark confidences.
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        min_frame_confidence: float = 0.4,
        process_noise_pos: float = 5e-3,
        process_noise_vel: float = 5e-2,
        measurement_noise: float = 2.0,
    ):
        self.min_conf = min_confidence
        self.min_frame_conf = min_frame_confidence
        self.kf = LandmarkKalmanFilter2D(
            n_landmarks=N_LANDMARKS,
            process_noise_pos=process_noise_pos,
            process_noise_vel=process_noise_vel,
            measurement_noise=measurement_noise,
            confidence_threshold=min_confidence,
        )
        self._frame_count: int = 0
        self._accepted: int = 0

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def update_from_mediapipe(
        self,
        landmarks: Any,       # mediapipe NormalizedLandmarkList
        world_landmarks: Any, # mediapipe NormalizedLandmarkList (world)
        image_width: int,
        image_height: int,
    ) -> dict[str, Any] | None:
        """
        Extract, filter and smooth MediaPipe landmarks.

        Returns
        -------
        dict with keys:
            px      : dict[name → (x_px, y_px, visibility)]
            world   : dict[name → (x_m, y_m, z_m)]
            conf    : dict[name → float]  per-landmark confidence
            frame_conf : float            mean frame confidence
        or None if frame confidence is too low.
        """
        self._frame_count += 1

        # Build raw arrays
        pts_px = np.zeros((N_LANDMARKS, 2), dtype=float)
        pts_world = np.zeros((N_LANDMARKS, 3), dtype=float)
        confs = np.zeros(N_LANDMARKS, dtype=float)

        lm = landmarks.landmark
        wlm = world_landmarks.landmark

        for mp_idx, name in MP_INDEX_MAP.items():
            i = _NAME_TO_IDX[name]
            pts_px[i] = [lm[mp_idx].x * image_width, lm[mp_idx].y * image_height]
            pts_world[i] = [wlm[mp_idx].x, wlm[mp_idx].y, wlm[mp_idx].z]
            confs[i] = float(getattr(lm[mp_idx], "visibility", 0.5))

        frame_conf = float(confs.mean())
        if frame_conf < self.min_frame_conf:
            return None

        # Smooth pixel coords with Kalman (world coords averaged separately)
        smooth_px = self.kf.update(pts_px, confs)

        self._accepted += 1

        px_dict: dict[str, tuple[float, float, float]] = {
            name: (smooth_px[i, 0], smooth_px[i, 1], float(confs[i]))
            for name, i in _NAME_TO_IDX.items()
        }
        world_dict: dict[str, tuple[float, float, float]] = {
            name: tuple(pts_world[i].tolist())   # type: ignore[misc]
            for name, i in _NAME_TO_IDX.items()
        }
        conf_dict: dict[str, float] = {
            name: float(confs[i]) for name, i in _NAME_TO_IDX.items()
        }

        return {
            "px": px_dict,
            "world": world_dict,
            "conf": conf_dict,
            "frame_conf": frame_conf,
        }

    def reset(self) -> None:
        self.kf.reset()
        self._frame_count = 0
        self._accepted = 0

    @property
    def acceptance_rate(self) -> float:
        if self._frame_count == 0:
            return 0.0
        return self._accepted / self._frame_count
