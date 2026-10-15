"""
Measurement Engine — orchestrates all body measurements.

Architecture (as recommended)
------------------------------
    MediaPipe Pose (stable anatomical landmarks)
        +
    YOLO segmentation (body silhouette for circumference widths)
        +
    Custom YOLO keypoints (tailor-specific points)
        ↓
    CameraGeometry (pixels → cm)
        ↓
    MeasurementEngine.compute()
        ↓
    {landmark measurements} + {circumference measurements}
        ↓
    BodyShapeCorrectionModel.correct_all()
        ↓
    Final measurements + confidence scores

Measurement categories
----------------------
A. Landmark measurements (from 3D points):
   shoulder_width, sleeve, upper_arm, half_length, full_length,
   torso, inseam, back_width

B. Circumference measurements (from front+side widths):
   bust, empire (under-bust), waist, hip, round_sleeve
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from app.core.circumference import ramanujan_perimeter, level_widths_cm, body_height_px, mask_width_px
from app.core.tailoring_regression import (
    BUSTIER_LENGTH_RATIO,
    SHOULDER_OFFSET_FACTOR,
    SKIRT_LENGTH_FACTOR,
)

# cm offset from nose to approximate crown of head
NOSE_TO_CROWN_CM = 11.5


class MeasurementEngine:
    """
    Converts stable 3D landmarks + segmentation masks to physical measurements.

    Parameters
    ----------
    world_scale : float
        Scale factor: world_coordinate * 100 * world_scale = centimetres.
        Set via set_scale() after calibration.
    """

    def __init__(self) -> None:
        self.world_scale: float | None = None
        self._scale_confidence: float = 0.0

    # ------------------------------------------------------------------
    # Scale calibration
    # ------------------------------------------------------------------

    @staticmethod
    def estimated_body_height_cm(world: Mapping[str, Sequence[float]]) -> float:
        """
        Estimate body height from MediaPipe world landmarks (metres).
        Adds NOSE_TO_CROWN_CM to account for the head above the nose.
        """
        heel_y = (world["l_heel"][1] + world["r_heel"][1]) / 2
        return abs(world["nose"][1] - heel_y) * 100 + NOSE_TO_CROWN_CM

    def set_scale(self, known_height_cm: float, estimated_height_cm: float) -> float:
        """Compute and store the world-to-cm scale factor."""
        if estimated_height_cm <= 0:
            raise ValueError("Cannot set scale: estimated height is zero or negative")
        self.world_scale = known_height_cm / estimated_height_cm
        return self.world_scale

    def set_scale_from_geometry(self, cm_per_px: float, height_px: float) -> None:
        """
        Set scale from camera geometry (e.g. ArUco marker or height-based).
        This is preferred over the world-landmark method when available.
        """
        # Store cm_per_px for pixel-level measurements
        self._cm_per_px = cm_per_px
        self._height_px = height_px

    def torso_is_plausible(
        self, world: Mapping[str, Sequence[float]], known_height_cm: float
    ) -> bool:
        """Sanity check: torso length should be 22–38 % of full height."""
        torso = math.dist(world["l_shoulder"], world["l_hip"]) * 100 * (self.world_scale or 1.0)
        return 0.22 <= torso / known_height_cm <= 0.38

    # ------------------------------------------------------------------
    # A. Landmark measurements (from 3D world coords)
    # ------------------------------------------------------------------

    def landmark_measurements(
        self,
        world: Mapping[str, Sequence[float]],
        custom_px: dict[str, tuple[float, float, float]] | None = None,
        cm_per_px: float | None = None,
    ) -> dict[str, float]:
        """
        Compute measurements from 3D world landmarks.

        All returned values are in centimetres.

        Parameters
        ----------
        world : MediaPipe world-landmark dict {name: (x, y, z)} in metres
        custom_px : optional custom YOLO keypoints {name: (x_px, y_px, conf)}
        cm_per_px : pixel-to-cm scale for custom_px measurements
        """
        scale = self.world_scale or 1.0

        def dist3d(a: str, b: str) -> float:
            return math.dist(world[a], world[b]) * 100 * scale

        def midpoint3d(a: str, b: str) -> tuple[float, float, float]:
            wa, wb = world[a], world[b]
            return ((wa[0] + wb[0]) / 2, (wa[1] + wb[1]) / 2, (wa[2] + wb[2]) / 2)

        # Core measurements from MediaPipe landmarks
        measurements: dict[str, float] = {
            # --- Widths ---
            "shoulder_width": dist3d("l_shoulder", "r_shoulder"),

            # --- Arm lengths ---
            "sleeve": dist3d("l_shoulder", "l_elbow") + dist3d("l_elbow", "l_wrist"),
            "upper_arm": dist3d("l_shoulder", "l_elbow"),

            # --- Vertical lengths ---
            "half_length": dist3d("l_shoulder", "l_hip"),
            "full_length": (
                dist3d("l_shoulder", "l_hip")
                + dist3d("l_hip", "l_knee")
                + dist3d("l_knee", "l_ankle")
            ),
            "torso": dist3d("l_shoulder", "l_hip"),
            "inseam": dist3d("l_hip", "l_knee") + dist3d("l_knee", "l_ankle"),

            # --- Hip width from hip landmarks ---
            "hip_width": dist3d("l_hip", "r_hip"),
        }

        # Back width: use shoulder width as a proxy until a back view is available.
        measurements["back_width"] = (
            measurements["shoulder_width"] * SHOULDER_OFFSET_FACTOR
        )
        measurements["blouse_length"] = measurements["half_length"]
        measurements["bustier_length"] = (
            measurements["half_length"] * BUSTIER_LENGTH_RATIO
        )
        measurements["skirt_length"] = (
            dist3d("l_hip", "l_ankle") * SKIRT_LENGTH_FACTOR
        )

        # Custom YOLO keypoint measurements (when available)
        if custom_px and cm_per_px and cm_per_px > 0:
            # Bust width (left to right bust points)
            if "bust_left" in custom_px and "bust_right" in custom_px:
                bx1, by1, bc1 = custom_px["bust_left"]
                bx2, by2, bc2 = custom_px["bust_right"]
                if min(bc1, bc2) > 0.3:
                    measurements["bust_width_custom"] = (
                        math.dist((bx1, by1), (bx2, by2)) * cm_per_px
                    )

            # Waist width (left to right waist points)
            if "waist_left" in custom_px and "waist_right" in custom_px:
                wx1, wy1, wc1 = custom_px["waist_left"]
                wx2, wy2, wc2 = custom_px["waist_right"]
                if min(wc1, wc2) > 0.3:
                    measurements["waist_width_custom"] = (
                        math.dist((wx1, wy1), (wx2, wy2)) * cm_per_px
                    )

            # Under-bust (empire) width
            if "underbust_left" in custom_px and "underbust_right" in custom_px:
                ex1, ey1, ec1 = custom_px["underbust_left"]
                ex2, ey2, ec2 = custom_px["underbust_right"]
                if min(ec1, ec2) > 0.3:
                    measurements["empire_width_custom"] = (
                        math.dist((ex1, ey1), (ex2, ey2)) * cm_per_px
                    )

        return measurements

    # ------------------------------------------------------------------
    # B. Circumference measurements (from front + side segmentation masks)
    # ------------------------------------------------------------------

    @staticmethod
    def circumference_measurements(
        front_mask: np.ndarray,
        side_mask: np.ndarray,
        front_shoulder_y: float,
        front_hip_y: float,
        known_height_cm: float,
    ) -> dict[str, float]:
        """
        Compute circumferences using Ramanujan's ellipse approximation.

        front_mask / side_mask : H×W float32 segmentation masks (0–1)
        front_shoulder_y / front_hip_y : pixel y-coords of shoulder and hip
        known_height_cm : person's known height for pixel-to-cm conversion

        Returns dict with bust, empire, waist, hip (all in cm, circumferences).
        """
        # Get widths at anatomical levels from front view
        front_widths = level_widths_cm(
            front_mask, front_shoulder_y, front_hip_y, known_height_cm
        )
        # Get depths at the same levels from side view
        side_depths = level_widths_cm(
            side_mask, front_shoulder_y, front_hip_y, known_height_cm
        )

        # Compute elliptical circumferences
        result: dict[str, float] = {}
        for level in ("bust", "empire", "waist", "hip"):
            w = front_widths.get(level, 0.0)
            d = side_depths.get(level, 0.0)
            if w > 5 and d > 5:  # Plausibility check
                result[level] = ramanujan_perimeter(w, d)
            else:
                result[level] = 0.0

        return result

    @staticmethod
    def round_sleeve_from_mask(
        front_mask: np.ndarray,
        shoulder_px: tuple[float, float],
        cm_per_px: float,
    ) -> float:
        """
        Estimate round-sleeve (upper arm circumference) from the arm region
        of the segmentation mask.

        Uses the mask width at the point ~15 % below the shoulder level.
        """
        y_ref = int(shoulder_px[1] + 0.15 * front_mask.shape[0])
        arm_width_px = mask_width_px(front_mask, y_ref)
        # The visible width is approx half the circumference (front view only)
        circumference_approx = arm_width_px * cm_per_px * math.pi / 2
        return circumference_approx

    # ------------------------------------------------------------------
    # C. Multi-view combination
    # ------------------------------------------------------------------

    def combine_views(
        self,
        front_landmark: dict[str, float],
        side_landmark: dict[str, float] | None,
        front_circumference: dict[str, float],
        back_landmark: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """
        Merge front, side, and (optionally) back view measurements into
        a single best-estimate set.

        Front view is authoritative for widths and lengths.
        Side view is used to update depth-dependent measurements.
        Back view refines back_width if available.
        """
        combined = dict(front_landmark)

        # Add circumferences (require both front + side)
        combined.update(front_circumference)

        # If side view available, update back-width estimate
        if side_landmark:
            # Side torso depth can refine waist estimate
            if "torso" in side_landmark and "torso" in combined:
                # Average front and side torso for a more balanced estimate
                combined["torso"] = (combined["torso"] + side_landmark["torso"]) / 2

        if back_landmark and "shoulder_width" in back_landmark:
            # Back view provides a direct back-width measurement
            combined["back_width"] = back_landmark["shoulder_width"]

        return combined

    # ------------------------------------------------------------------
    # D. Per-measurement confidence scoring
    # ------------------------------------------------------------------

    @staticmethod
    def confidence_scores(
        measurements: dict[str, float],
        world_scale: float | None,
        frame_conf: float,
        has_segmentation: bool,
        has_side_view: bool,
        has_custom_keypoints: bool,
    ) -> dict[str, float]:
        """
        Compute a confidence score (0–1) for each measurement.

        Confidence reflects:
        - Frame-level detection quality
        - Whether scale calibration is available
        - Whether additional views / segmentation are available
        - Whether the measurement requires depth (circumferences suffer more)
        """
        base = frame_conf * (0.85 if world_scale else 0.5)
        scores: dict[str, float] = {}

        for name in measurements:
            conf = base
            # Circumferences need segmentation and side view
            if name in ("bust", "empire", "waist", "hip", "round_sleeve"):
                if not has_segmentation:
                    conf *= 0.5
                if not has_side_view:
                    conf *= 0.6
            # Custom keypoint measurements
            if name.endswith("_custom"):
                conf *= (0.85 if has_custom_keypoints else 0.4)
            scores[name] = round(min(max(conf, 0.0), 1.0), 3)

        return scores
