import math

import numpy as np


def ramanujan_perimeter(width_cm: float, depth_cm: float) -> float:
    semi_width, semi_depth = width_cm / 2, depth_cm / 2
    return math.pi * (
        3 * (semi_width + semi_depth)
        - math.sqrt((3 * semi_width + semi_depth) * (semi_width + 3 * semi_depth))
    )


def mask_width_px(mask: np.ndarray, row: int, thresh: float = 0.5) -> float:
    row = min(max(row, 0), mask.shape[0] - 1)
    columns = np.where(mask[row] > thresh)[0]
    return float(columns.max() - columns.min()) if columns.size else 0.0


def body_height_px(mask: np.ndarray, thresh: float = 0.5) -> float:
    rows = np.where((mask > thresh).any(axis=1))[0]
    return float(rows.max() - rows.min()) if rows.size else 0.0


def level_widths_cm(
    mask: np.ndarray, y_shoulder: float, y_hip: float, known_height_cm: float
) -> dict[str, float]:
    body_height = body_height_px(mask)
    if body_height <= 0:
        return {"bust": 0.0, "waist": 0.0, "hip": 0.0}
    cm_per_px = known_height_cm / body_height
    span = y_hip - y_shoulder
    rows = {
        "bust": y_shoulder + 0.30 * span,
        "waist": y_shoulder + 0.68 * span,
        "hip": y_hip + 0.12 * span,
    }
    return {name: mask_width_px(mask, int(row)) * cm_per_px for name, row in rows.items()}


def combine(front: dict[str, float], side: dict[str, float]) -> dict[str, float]:
    return {
        name: ramanujan_perimeter(front[name], side[name])
        for name in ("bust", "waist", "hip")
    }
