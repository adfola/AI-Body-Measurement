"""
Per-landmark Kalman filter with 4-state tracking: [x, y, vx, vy].

The filter stabilises frame-to-frame jitter from MediaPipe / YOLO landmark
detections.  Each landmark is tracked independently so noisy or occluded
landmarks do not contaminate neighbouring joints.

Architecture note
-----------------
Kalman filtering belongs *before* the measurement engine, not after.
Run raw detector landmarks → confidence check → Kalman → stable landmarks →
measurement calculation.  The filter suppresses jitter; it does **not** fix
a systematic detector bias (that is the job of the correction model).
"""
from __future__ import annotations

import numpy as np


class LandmarkKalmanFilter:
    """
    Scalar Kalman filter for a flat vector of coordinates.

    Keeps the existing interface so existing call sites (stream.py) continue
    to work unchanged while the per-landmark variant is used for new code.
    """

    def __init__(self, process_noise: float = 1e-3, measurement_noise: float = 1e-1):
        self.q = process_noise
        self.r = measurement_noise
        self.x: np.ndarray | None = None
        self.p: np.ndarray | None = None

    def update(self, z: np.ndarray) -> np.ndarray:
        if self.x is None:
            self.x = z.astype(float)
            self.p = np.ones_like(z, dtype=float)
            return self.x.copy()
        p_prior = self.p + self.q
        gain = p_prior / (p_prior + self.r)
        self.x = self.x + gain * (z - self.x)
        self.p = (1 - gain) * p_prior
        return self.x.copy()

    def reset(self) -> None:
        self.x = None
        self.p = None


class LandmarkKalmanFilter2D:
    """
    Per-landmark Kalman filter with 4-state tracking: position + velocity.

    State vector per landmark: [x, y, vx, vy]
    Measurement vector:        [x, y]

    This gives smoother, more physically plausible landmark trajectories
    compared to the scalar filter and is the recommended choice for new
    measurement code.

    Usage
    -----
    kf = LandmarkKalmanFilter2D(n_landmarks=33)
    for frame in video:
        pts, confs = detect(frame)          # (33, 2) and (33,)
        stable_pts = kf.update(pts, confs)  # (33, 2) smoothed
    """

    def __init__(
        self,
        n_landmarks: int,
        dt: float = 1.0,
        process_noise_pos: float = 1e-2,
        process_noise_vel: float = 1e-1,
        measurement_noise: float = 1.0,
        confidence_threshold: float = 0.3,
    ):
        self.n = n_landmarks
        self.dt = dt
        self.conf_thresh = confidence_threshold

        # State: [x, y, vx, vy] per landmark  →  shape (n, 4)
        self.x = np.zeros((n_landmarks, 4), dtype=float)
        # Covariance diagonal per landmark  →  shape (n, 4)
        self.p = np.ones((n_landmarks, 4), dtype=float) * 1e2

        # Transition matrix  4×4  (constant-velocity model)
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1,  0],
            [0, 0, 0,  1],
        ], dtype=float)

        # Observation matrix  2×4  (observe x, y only)
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=float)

        # Process noise covariance 4×4
        q_pos = process_noise_pos
        q_vel = process_noise_vel
        self.Q = np.diag([q_pos, q_pos, q_vel, q_vel])

        # Measurement noise covariance 2×2
        self.R = np.eye(2, dtype=float) * measurement_noise

        self._initialised = np.zeros(n_landmarks, dtype=bool)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        measurements: np.ndarray,
        confidences: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Parameters
        ----------
        measurements : np.ndarray shape (n, 2)
            Raw (x, y) pixel or world coordinates from the detector.
        confidences : np.ndarray shape (n,) | None
            Per-landmark visibility / confidence scores [0, 1].
            Landmarks below ``self.conf_thresh`` are predicted-only (no update).

        Returns
        -------
        np.ndarray shape (n, 2)  — smoothed (x, y) positions.
        """
        if confidences is None:
            confidences = np.ones(self.n, dtype=float)

        out = np.zeros((self.n, 2), dtype=float)

        for i in range(self.n):
            z = measurements[i]  # (2,)
            conf = float(confidences[i])

            if not self._initialised[i]:
                # Cold-start: seed state from first measurement
                self.x[i] = [z[0], z[1], 0.0, 0.0]
                self.p[i] = [1e2, 1e2, 1e2, 1e2]
                self._initialised[i] = True
                out[i] = z
                continue

            # ---- Predict ----
            x_pred = self.F @ self.x[i]                         # (4,)
            p_pred = self.F @ np.diag(self.p[i]) @ self.F.T + self.Q  # (4,4)

            if conf < self.conf_thresh:
                # Low-confidence: propagate prediction without update
                self.x[i] = x_pred
                self.p[i] = np.diag(p_pred)
                out[i] = x_pred[:2]
                continue

            # ---- Update ----
            # Innovation
            y = z - self.H @ x_pred                             # (2,)
            # Scale measurement noise by inverse confidence
            R_scaled = self.R / max(conf, 1e-3)
            S = self.H @ p_pred @ self.H.T + R_scaled           # (2,2)
            K = p_pred @ self.H.T @ np.linalg.inv(S)           # (4,2)

            self.x[i] = x_pred + K @ y                          # (4,)
            self.p[i] = np.diag((np.eye(4) - K @ self.H) @ p_pred)

            out[i] = self.x[i, :2]

        return out

    def reset(self) -> None:
        self.x[:] = 0
        self.p[:] = 1e2
        self._initialised[:] = False

    def predicted_positions(self) -> np.ndarray:
        """Return current predicted (x, y) for all landmarks without update."""
        return self.x[:, :2].copy()
