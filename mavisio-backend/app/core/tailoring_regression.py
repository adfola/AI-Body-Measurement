"""
Tailoring Regression Engine — height-grounded body measurement.

Solves the accuracy problem by combining:
1. Customer height grounding (dynamic per scan, never hardcoded)
2. Elliptical 3D circumferences via Ramanujan's approximation
3. Female tailoring proportion mapping (ISO 8559 garment standards)

Usage
-----
    engine = TailoringRegressionEngine(actual_height_cm=168.0)
    result = engine.predict_tailoring_measurements(
        landmarks=detected_landmarks,
        image_height_px=1080,
    )
    print(result["measurements_cm"])
    print(result["measurements_inches"])
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


# ────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────

CM_PER_INCH = 2.54

# Nose-to-crown offset (MediaPipe "nose" is ~11.5 cm below the real
# top of the head for an average adult).
NOSE_TO_CROWN_CM = 11.5

# Anthropometric depth-to-width ratios for single-frontal-view
# circumference estimation.  Derived from ANSUR II female dataset and
# ISO 8559-1 body-measurement standards.
DEPTH_RATIO: dict[str, float] = {
    "bust":       0.72,   # depth ≈ 72 % of front width
    "empire":     0.68,   # under-bust slightly flatter
    "waist":      0.65,   # waist is typically more oval
    "hip":        0.70,   # hip is rounder
    "round_sleeve": 0.85, # upper arm is nearly circular
}

# Tailoring offset factors (seam-allowance multipliers)
SHOULDER_OFFSET_FACTOR = 1.06   # seam + ease
SKIRT_LENGTH_FACTOR    = 1.08   # hem + ease
HALF_LENGTH_FACTOR     = 0.78   # natural waist drop
BUSTIER_LENGTH_RATIO   = 0.64   # bustier ≈ 64 % of half-length


# ────────────────────────────────────────────────────────────────────
# Ramanujan Ellipse Perimeter
# ────────────────────────────────────────────────────────────────────

def ramanujan_circumference(width_cm: float, depth_cm: float) -> float:
    """
    Ramanujan's approximation for an ellipse perimeter.

        C ≈ π [ 3(a+b) − √((3a+b)(a+3b)) ]

    where a = width/2 (semi-major) and b = depth/2 (semi-minor).
    """
    if width_cm <= 0 or depth_cm <= 0:
        return 0.0
    a = width_cm / 2
    b = depth_cm / 2
    return math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))


# ────────────────────────────────────────────────────────────────────
# Main Engine
# ────────────────────────────────────────────────────────────────────

class TailoringRegressionEngine:
    """
    Height-grounded body measurement engine.

    Parameters
    ----------
    actual_height_cm : float
        The customer's verified height in centimetres.
        Each customer session passes their own unique height.
    """

    def __init__(self, actual_height_cm: float) -> None:
        if not 50 <= actual_height_cm <= 250:
            raise ValueError(
                f"Height must be between 50 and 250 cm, got {actual_height_cm}"
            )
        self.actual_height_cm = actual_height_cm
        self._scale_cm_per_px: float | None = None

    # ──────────────────────────────────────────────────────────────
    # Scale calibration
    # ──────────────────────────────────────────────────────────────

    def compute_scale(
        self,
        head_top_y_px: float,
        heel_y_px: float,
    ) -> float:
        """
        Compute the unique pixel-to-cm scale factor for this customer
        from the detected body extent in the image.

        Scale = actual_height_cm / body_pixel_height
        """
        body_height_px = abs(heel_y_px - head_top_y_px)
        if body_height_px < 30:
            raise ValueError("Body pixel height too small — body not fully visible")
        self._scale_cm_per_px = self.actual_height_cm / body_height_px
        return self._scale_cm_per_px

    @property
    def scale(self) -> float | None:
        return self._scale_cm_per_px

    # ──────────────────────────────────────────────────────────────
    # Pixel distance helpers
    # ──────────────────────────────────────────────────────────────

    def _px_dist(
        self,
        pt_a: Sequence[float],
        pt_b: Sequence[float],
    ) -> float:
        """Euclidean distance between two pixel-coordinate points."""
        return math.dist(pt_a[:2], pt_b[:2])

    def _px_to_cm(self, pixels: float) -> float:
        """Convert a pixel distance to cm using the grounded scale."""
        if self._scale_cm_per_px is None:
            raise RuntimeError("Scale not computed — call compute_scale() first")
        return pixels * self._scale_cm_per_px

    # ──────────────────────────────────────────────────────────────
    # Circumference estimation (single frontal view)
    # ──────────────────────────────────────────────────────────────

    def estimate_circumference(
        self,
        frontal_width_cm: float,
        body_part: str,
        side_depth_cm: float | None = None,
    ) -> float:
        """
        Estimate 3D circumference from a frontal width measurement.

        If side_depth_cm is provided (front + side scan), uses that.
        Otherwise, applies the anthropometric depth ratio for the body part.
        """
        if side_depth_cm is not None and side_depth_cm > 0:
            depth = side_depth_cm
        else:
            ratio = DEPTH_RATIO.get(body_part, 0.70)
            depth = frontal_width_cm * ratio

        return ramanujan_circumference(frontal_width_cm, depth)

    # ──────────────────────────────────────────────────────────────
    # Main prediction
    # ──────────────────────────────────────────────────────────────

    def predict_tailoring_measurements(
        self,
        landmarks: Mapping[str, Sequence[float]],
        image_height_px: int = 1000,
        side_landmarks: Mapping[str, Sequence[float]] | None = None,
        scale_cm_per_px: float | None = None,
    ) -> dict[str, Any]:
        """
        Produce a full tailoring measurement sheet from detected landmarks.

        Parameters
        ----------
        landmarks : dict
            Pixel-coordinate landmarks {name: (x_px, y_px, ...)}
            Must include: nose, l_shoulder, r_shoulder, l_hip, r_hip,
            l_elbow, l_wrist, l_knee, l_ankle, l_heel, r_heel.
        image_height_px : int
            Height of the source frame in pixels.
        side_landmarks : dict | None
            Optional side-view landmarks for improved circumference depth.

        Returns
        -------
        dict with:
            scale_cm_per_px : float
            measurements_cm : dict[str, float]
            measurements_inches : dict[str, float]
        """
        if image_height_px <= 0:
            raise ValueError("Image height must be greater than zero")

        # ── Step 1: Height-grounded scale ──
        left_heel = landmarks.get("l_heel", landmarks.get("l_ankle"))
        right_heel = landmarks.get("r_heel", landmarks.get("r_ankle"))
        if left_heel is None or right_heel is None:
            raise ValueError("Heel or ankle landmarks are required for height scaling")
        heel_y = (left_heel[1] + right_heel[1]) / 2
        if scale_cm_per_px is not None:
            if scale_cm_per_px <= 0:
                raise ValueError("Pixel scale must be greater than zero")
            self._scale_cm_per_px = scale_cm_per_px
        else:
            nose_y = landmarks["nose"][1]
            nose_to_heel_px = abs(heel_y - nose_y)
            if nose_to_heel_px < 30:
                raise ValueError("Cannot compute scale — body not fully visible")
            crown_ratio = NOSE_TO_CROWN_CM / self.actual_height_cm
            nose_to_crown_px = crown_ratio * nose_to_heel_px / (1 - crown_ratio)
            self.compute_scale(nose_y - nose_to_crown_px, heel_y)

        # ── Step 2: Linear tailoring measurements ──
        measurements_cm: dict[str, float] = {}

        # Full Length — directly matches customer's input height
        measurements_cm["full_length"] = self.actual_height_cm

        # Shoulder Width
        shoulder_width_px = self._px_dist(
            landmarks["l_shoulder"], landmarks["r_shoulder"]
        )
        measurements_cm["shoulder_width"] = self._px_to_cm(shoulder_width_px)

        # Back Width — shoulder width × offset factor for seam allowance
        measurements_cm["back_width"] = (
            measurements_cm["shoulder_width"] * SHOULDER_OFFSET_FACTOR
        )

        # Sleeve — shoulder to elbow + elbow to wrist
        upper_arm_px = self._px_dist(landmarks["l_shoulder"], landmarks["l_elbow"])
        forearm_px = self._px_dist(landmarks["l_elbow"], landmarks["l_wrist"])
        measurements_cm["sleeve"] = self._px_to_cm(upper_arm_px + forearm_px)
        measurements_cm["upper_arm"] = self._px_to_cm(upper_arm_px)

        # Half Length (Blouse Length) — shoulder to hip vertical × factor
        shoulder_mid_y = (landmarks["l_shoulder"][1] + landmarks["r_shoulder"][1]) / 2
        hip_mid_y = (landmarks["l_hip"][1] + landmarks["r_hip"][1]) / 2
        shoulder_to_hip_px = abs(hip_mid_y - shoulder_mid_y)
        half_length_cm = self._px_to_cm(shoulder_to_hip_px)
        measurements_cm["half_length"] = half_length_cm
        measurements_cm["blouse_length"] = half_length_cm

        # Torso
        measurements_cm["torso"] = half_length_cm

        # Bustier Length — shoulder midpoint to bust point
        measurements_cm["bustier_length"] = half_length_cm * BUSTIER_LENGTH_RATIO

        # Skirt Length — waist (approx hip) to ankle × factor
        ankle_y = landmarks["l_ankle"][1]
        waist_to_ankle_px = abs(ankle_y - hip_mid_y)
        measurements_cm["skirt_length"] = (
            self._px_to_cm(waist_to_ankle_px) * SKIRT_LENGTH_FACTOR
        )

        # Inseam — hip to knee + knee to ankle
        hip_to_knee_px = self._px_dist(landmarks["l_hip"], landmarks["l_knee"])
        knee_to_ankle_px = self._px_dist(landmarks["l_knee"], landmarks["l_ankle"])
        measurements_cm["inseam"] = self._px_to_cm(hip_to_knee_px + knee_to_ankle_px)

        # Hip width (linear, for reference)
        hip_width_px = self._px_dist(landmarks["l_hip"], landmarks["r_hip"])
        measurements_cm["hip_width"] = self._px_to_cm(hip_width_px)

        # ── Step 3: Circumference estimations ──
        # Bust — estimate from shoulder-to-hip span interpolation
        bust_y = shoulder_mid_y + 0.30 * shoulder_to_hip_px
        bust_width_cm = self._estimate_body_width_at_y(
            landmarks, bust_y, "bust"
        )
        side_bust_depth = None
        if side_landmarks:
            side_bust_depth = self._estimate_body_width_at_y(
                side_landmarks, bust_y, "bust"
            )
        measurements_cm["bust"] = self.estimate_circumference(
            bust_width_cm, "bust", side_bust_depth
        )

        # Empire (Under-bust)
        empire_y = shoulder_mid_y + 0.45 * shoulder_to_hip_px
        empire_width_cm = self._estimate_body_width_at_y(
            landmarks, empire_y, "empire"
        )
        side_empire_depth = None
        if side_landmarks:
            side_empire_depth = self._estimate_body_width_at_y(
                side_landmarks, empire_y, "empire"
            )
        measurements_cm["empire"] = self.estimate_circumference(
            empire_width_cm, "empire", side_empire_depth
        )

        # Waist
        waist_y = shoulder_mid_y + 0.68 * shoulder_to_hip_px
        waist_width_cm = self._estimate_body_width_at_y(
            landmarks, waist_y, "waist"
        )
        side_waist_depth = None
        if side_landmarks:
            side_waist_depth = self._estimate_body_width_at_y(
                side_landmarks, waist_y, "waist"
            )
        measurements_cm["waist"] = self.estimate_circumference(
            waist_width_cm, "waist", side_waist_depth
        )

        # Hip circumference
        hip_circumference_y = hip_mid_y + 0.12 * shoulder_to_hip_px
        hip_circ_width_cm = self._estimate_body_width_at_y(
            landmarks, hip_circumference_y, "hip"
        )
        side_hip_depth = None
        if side_landmarks:
            side_hip_depth = self._estimate_body_width_at_y(
                side_landmarks, hip_circumference_y, "hip"
            )
        measurements_cm["hip"] = self.estimate_circumference(
            hip_circ_width_cm, "hip", side_hip_depth
        )

        # Round Sleeve (upper arm circumference)
        # Bicep width from arm contour at ~15% below shoulder
        # Approximate bicep width from elbow-shoulder geometry
        bicep_width_px = upper_arm_px * 0.35  # bicep is ~35% of upper arm length
        bicep_width_cm = self._px_to_cm(bicep_width_px)
        measurements_cm["round_sleeve"] = self.estimate_circumference(
            bicep_width_cm, "round_sleeve"
        )

        # ── Step 4: Convert to inches ──
        measurements_inches = {
            name: round(val / CM_PER_INCH, 1)
            for name, val in measurements_cm.items()
        }

        # Round cm values
        measurements_cm = {
            name: round(val, 1) for name, val in measurements_cm.items()
        }

        return {
            "scale_cm_per_px": round(self._scale_cm_per_px, 6),
            "measurements_cm": measurements_cm,
            "measurements_inches": measurements_inches,
        }

    # ──────────────────────────────────────────────────────────────
    # Width estimation at arbitrary Y from landmarks
    # ──────────────────────────────────────────────────────────────

    def _estimate_body_width_at_y(
        self,
        landmarks: Mapping[str, Sequence[float]],
        target_y: float,
        body_part: str,
    ) -> float:
        """
        Estimate body width at a given Y coordinate by interpolating
        between shoulder and hip widths based on Y position.
        """
        shoulder_mid_y = (landmarks["l_shoulder"][1] + landmarks["r_shoulder"][1]) / 2
        hip_mid_y = (landmarks["l_hip"][1] + landmarks["r_hip"][1]) / 2

        shoulder_width_px = self._px_dist(
            landmarks["l_shoulder"], landmarks["r_shoulder"]
        )
        hip_width_px = self._px_dist(landmarks["l_hip"], landmarks["r_hip"])

        span = hip_mid_y - shoulder_mid_y
        if span <= 0:
            return self._px_to_cm(shoulder_width_px)

        # Linear interpolation factor (0 = shoulder level, 1 = hip level)
        t = max(0.0, min(1.0, (target_y - shoulder_mid_y) / span))

        # Body width follows a characteristic curve:
        # wider at bust and hip, narrower at waist
        if body_part == "waist":
            # Waist is typically narrower than linear interpolation
            width_px = shoulder_width_px * (1 - t) + hip_width_px * t
            width_px *= 0.85  # waist cinch factor
        elif body_part == "bust":
            # Bust is slightly wider than shoulder interpolation
            width_px = shoulder_width_px * (1 - t) + hip_width_px * t
            width_px *= 1.08  # bust prominence factor
        elif body_part == "hip":
            # Hip is wider than linear interpolation
            width_px = hip_width_px * 1.12
        else:
            width_px = shoulder_width_px * (1 - t) + hip_width_px * t

        return self._px_to_cm(width_px)
