"""
Circumference calculation engine.

Uses Ramanujan's ellipse circumference approximation:
    C ≈ π [ 3(a+b) − √((3a+b)(a+3b)) ]

where a = front_width/2 and b = side_depth/2.

This is much more defensible than multiplying front width by a magic number.
For production accuracy, combine with a learned correction model trained on
real tape measurements.
"""
from __future__ import annotations

import math

import numpy as np


def ramanujan_perimeter(width_cm: float, depth_cm: float) -> float:
    """
    Approximate circumference of an elliptical cross-section.

    Parameters
    ----------
    width_cm : outer width (front-view) in centimetres
    depth_cm : outer depth (side-view) in centimetres

    Returns
    -------
    Circumference estimate in centimetres.
    """
    if width_cm <= 0 or depth_cm <= 0:
        return 0.0
    a = width_cm / 2  # semi-major axis
    b = depth_cm / 2  # semi-minor axis
    return math.pi * (
        3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b))
    )


def mask_width_px(mask: np.ndarray, row: int, thresh: float = 0.5) -> float:
    """
    Return the horizontal span of the body mask at a given pixel row.

    Parameters
    ----------
    mask : H×W float32 array (values 0–1)
    row  : pixel y-coordinate (clamped to valid range)
    thresh : mask binarisation threshold

    Returns
    -------
    Width in pixels, or 0.0 if the row is empty.
    """
    row = int(min(max(row, 0), mask.shape[0] - 1))
    columns = np.where(mask[row] > thresh)[0]
    return float(columns.max() - columns.min()) if columns.size > 1 else 0.0


def body_height_px(mask: np.ndarray, thresh: float = 0.5) -> float:
    """
    Return the vertical span (head-to-toe) of the body mask in pixels.

    Parameters
    ----------
    mask : H×W float32 array
    thresh : binarisation threshold

    Returns
    -------
    Height in pixels, or 0.0 if the mask is empty.
    """
    rows = np.where((mask > thresh).any(axis=1))[0]
    return float(rows.max() - rows.min()) if rows.size > 1 else 0.0


def body_top_bottom_px(mask: np.ndarray, thresh: float = 0.5) -> tuple[float, float]:
    """Return (top_y, bottom_y) pixel rows of the body mask."""
    rows = np.where((mask > thresh).any(axis=1))[0]
    if rows.size < 2:
        return 0.0, float(mask.shape[0])
    return float(rows.min()), float(rows.max())


def level_widths_cm(
    mask: np.ndarray,
    y_shoulder: float,
    y_hip: float,
    known_height_cm: float,
) -> dict[str, float]:
    """
    Extract body widths at anatomical levels from a segmentation mask.

    Anatomical level positions (fraction of shoulder→hip span):
        bust    : 30 % below shoulder
        empire  : 45 % below shoulder (under-bust)
        waist   : 68 % below shoulder
        hip     : 12 % below hip

    Parameters
    ----------
    mask : H×W float32 segmentation mask
    y_shoulder : pixel y-coordinate of shoulder (front view)
    y_hip : pixel y-coordinate of hip (front view)
    known_height_cm : person's known height for cm/px conversion

    Returns
    -------
    dict with "bust", "empire", "waist", "hip" widths in centimetres.
    """
    body_h = body_height_px(mask)
    if body_h <= 0:
        return {"bust": 0.0, "empire": 0.0, "waist": 0.0, "hip": 0.0}

    cm_per_px = known_height_cm / body_h
    span = y_hip - y_shoulder

    rows: dict[str, float] = {
        "bust":   y_shoulder + 0.30 * span,
        "empire": y_shoulder + 0.45 * span,
        "waist":  y_shoulder + 0.68 * span,
        "hip":    y_hip      + 0.12 * span,
    }
    return {
        name: mask_width_px(mask, int(row)) * cm_per_px
        for name, row in rows.items()
    }


def level_widths_cm_from_scale(
    mask: np.ndarray,
    y_shoulder: float,
    y_hip: float,
    cm_per_px: float,
) -> dict[str, float]:
    """
    Same as level_widths_cm but uses an externally provided cm_per_px scale
    (e.g. from ArUco marker or camera geometry — more accurate than height).

    Parameters
    ----------
    mask : H×W float32 segmentation mask
    y_shoulder : pixel y of shoulder
    y_hip : pixel y of hip
    cm_per_px : calibrated centimetres-per-pixel scale factor
    """
    span = y_hip - y_shoulder
    rows: dict[str, float] = {
        "bust":   y_shoulder + 0.30 * span,
        "empire": y_shoulder + 0.45 * span,
        "waist":  y_shoulder + 0.68 * span,
        "hip":    y_hip      + 0.12 * span,
    }
    return {
        name: mask_width_px(mask, int(row)) * cm_per_px
        for name, row in rows.items()
    }


def combine(
    front: dict[str, float],
    side: dict[str, float],
    levels: tuple[str, ...] = ("bust", "empire", "waist", "hip"),
) -> dict[str, float]:
    """
    Combine front widths and side depths into elliptical circumferences.

    Only computes circumference for levels present in both dicts and where
    both widths are positive (plausible values).

    Parameters
    ----------
    front : dict of level_name → width_cm (from front view mask)
    side  : dict of level_name → depth_cm (from side view mask)
    levels : which anatomical levels to combine

    Returns
    -------
    dict of level_name → circumference_cm
    """
    result: dict[str, float] = {}
    for name in levels:
        w = front.get(name, 0.0)
        d = side.get(name, 0.0)
        if w > 5 and d > 5:  # Minimum plausibility threshold
            result[name] = ramanujan_perimeter(w, d)
    return result


def round_sleeve_circumference(
    mask: np.ndarray,
    shoulder_y: float,
    cm_per_px: float,
    fraction_below: float = 0.10,
) -> float:
    """
    Estimate round-sleeve (upper arm) circumference from a front-view mask.

    Approximation: the visible arm width at the measurement level equals
    approximately half the true circumference (front view only).
    Multiply by π/2 to estimate the full circumference.

    Parameters
    ----------
    mask : H×W float32 segmentation mask (front view)
    shoulder_y : pixel y-coordinate of shoulder
    cm_per_px : calibrated scale
    fraction_below : how far below shoulder_y to sample (default 10 %)
    """
    sample_y = int(shoulder_y + fraction_below * mask.shape[0])
    arm_width_px = mask_width_px(mask, sample_y)
    if arm_width_px <= 0:
        return 0.0
    return arm_width_px * cm_per_px * math.pi / 2
