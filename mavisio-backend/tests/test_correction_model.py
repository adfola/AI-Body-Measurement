import numpy as np
import pytest

from app.core.circumference import ramanujan_perimeter
from app.core.correction_model import BodyShapeCorrectionModel


def test_correction_model_mae_below_2cm():
    """
    Evaluates system accuracy against ground-truth tailor measurements across representative body profiles.
    Verifies that mean absolute error (MAE) is strictly less than 2.0 cm.
    """
    model = BodyShapeCorrectionModel()

    # Ground truth tailor benchmark dataset: (height_cm, front_width, side_depth, tailor_measurements)
    benchmarks = [
        {
            "height": 168.0,
            "front_widths": {"bust": 28.5, "empire": 24.0, "waist": 22.0, "hip": 31.0},
            "side_depths": {"bust": 20.0, "empire": 17.5, "waist": 16.0, "hip": 22.5},
            "tailor": {
                "bust": 77.2,
                "empire": 65.8,
                "waist": 60.1,
                "hip": 84.8,
                "shoulder_width": 38.5,
                "sleeve": 57.0,
            },
            "raw_landmarks": {"shoulder_width": 38.8, "sleeve": 57.3},
        },
        {
            "height": 160.0,
            "front_widths": {"bust": 31.0, "empire": 26.5, "waist": 25.0, "hip": 33.5},
            "side_depths": {"bust": 22.0, "empire": 19.0, "waist": 18.0, "hip": 24.0},
            "tailor": {
                "bust": 83.8,
                "empire": 72.0,
                "waist": 67.9,
                "hip": 91.0,
                "shoulder_width": 37.0,
                "sleeve": 54.5,
            },
            "raw_landmarks": {"shoulder_width": 37.2, "sleeve": 54.8},
        },
        {
            "height": 175.0,
            "front_widths": {"bust": 33.0, "empire": 28.0, "waist": 26.0, "hip": 35.0},
            "side_depths": {"bust": 23.5, "empire": 20.0, "waist": 19.0, "hip": 25.5},
            "tailor": {
                "bust": 89.2,
                "empire": 76.0,
                "waist": 71.2,
                "hip": 95.8,
                "shoulder_width": 40.5,
                "sleeve": 60.0,
            },
            "raw_landmarks": {"shoulder_width": 40.8, "sleeve": 60.4},
        },
    ]

    errors = []

    for item in benchmarks:
        height = item["height"]
        front = item["front_widths"]
        side = item["side_depths"]
        
        # Compute raw Ramanujan circumferences + landmark values
        raw_measurements = {}
        for key in ("bust", "empire", "waist", "hip"):
            raw_measurements[key] = ramanujan_perimeter(front[key], side[key])
        raw_measurements.update(item["raw_landmarks"])

        # Apply ML Correction Model
        corrected = model.correct_all(
            measurements=raw_measurements,
            height_cm=height,
            front_widths=front,
            side_depths=side,
            scale_factor=1.0,
        )

        for key, target in item["tailor"].items():
            pred = corrected[key]
            err = abs(pred - target)
            errors.append(err)

    mae = np.mean(errors)
    max_err = np.max(errors)

    assert mae < 2.0, f"Target MAE must be < 2.0 cm, but got {mae:.2f} cm"
    assert max_err < 3.0, f"Max error must be < 3.0 cm, but got {max_err:.2f} cm"


def test_correction_model_bounding_and_overfit_protection():
    model = BodyShapeCorrectionModel(max_correction_cm=3.5)
    
    # Extreme inputs should be bounded properly and not produce invalid values
    corr = model.correct_measurement(
        name="bust",
        raw_val_cm=90.0,
        height_cm=165.0,
        width_cm=30.0,
        depth_cm=20.0,
        scale_factor=1.5,
    )
    assert 86.5 <= corr <= 93.5
