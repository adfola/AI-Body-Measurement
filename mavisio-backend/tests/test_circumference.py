import math

import numpy as np

from app.core.circumference import mask_width_px, ramanujan_perimeter


def test_circle():
    assert abs(ramanujan_perimeter(20, 20) - math.pi * 20) < 1e-6


def test_mask_width():
    mask = np.zeros((100, 100))
    mask[:, 40:60] = 1
    assert mask_width_px(mask, 50) == 19.0
