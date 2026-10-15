import pytest

from app.core.tailoring_regression import TailoringRegressionEngine, ramanujan_circumference


def make_landmarks(include_heels: bool = True) -> dict[str, tuple[float, float, float]]:
    landmarks = {
        "nose": (50, 100, 1),
        "l_shoulder": (30, 250, 1),
        "r_shoulder": (70, 250, 1),
        "l_elbow": (25, 370, 1),
        "l_wrist": (20, 480, 1),
        "l_hip": (35, 500, 1),
        "r_hip": (65, 500, 1),
        "l_knee": (38, 700, 1),
        "l_ankle": (40, 870, 1),
        "r_ankle": (60, 870, 1),
    }
    if include_heels:
        landmarks["l_heel"] = (40, 900, 1)
        landmarks["r_heel"] = (60, 900, 1)
    return landmarks


def test_height_grounded_output_includes_tailoring_lengths_and_inches():
    engine = TailoringRegressionEngine(actual_height_cm=180)

    result = engine.predict_tailoring_measurements(make_landmarks())

    assert result["measurements_cm"]["full_length"] == 180
    assert result["measurements_inches"]["full_length"] == 70.9
    assert result["measurements_cm"]["back_width"] > result["measurements_cm"]["shoulder_width"]
    assert result["measurements_cm"]["blouse_length"] == result["measurements_cm"]["half_length"]
    assert result["measurements_cm"]["skirt_length"] > 0
    assert result["measurements_cm"]["bustier_length"] > 0
    assert result["measurements_cm"]["round_sleeve"] > 0
    assert result["scale_cm_per_px"] > 0


def test_ankle_landmarks_can_ground_yolo_fallback_scale():
    result = TailoringRegressionEngine(180).predict_tailoring_measurements(
        make_landmarks(include_heels=False)
    )

    assert result["scale_cm_per_px"] > 0


def test_pixel_scale_override_is_used():
    result = TailoringRegressionEngine(180).predict_tailoring_measurements(
        make_landmarks(),
        scale_cm_per_px=0.2,
    )

    assert result["scale_cm_per_px"] == 0.2
    assert result["measurements_cm"]["shoulder_width"] == 8.0


def test_invalid_pixel_scale_is_rejected():
    with pytest.raises(ValueError, match="Pixel scale"):
        TailoringRegressionEngine(180).predict_tailoring_measurements(
            make_landmarks(),
            scale_cm_per_px=0,
        )


def test_ramanujan_ellipse_perimeter_matches_circle():
    assert ramanujan_circumference(20, 20) == pytest.approx(20 * 3.141592653589793)
