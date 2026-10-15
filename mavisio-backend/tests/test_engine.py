from app.core.measurement_engine import MeasurementEngine


def test_scale_and_tailoring_measurements():
    engine = MeasurementEngine()
    assert abs(engine.set_scale(165, 150) - 1.1) < 1e-9
    world = {
        "l_shoulder": (0, 0, 0), "r_shoulder": (0.4, 0, 0),
        "l_elbow": (0, 0.3, 0), "l_wrist": (0, 0.55, 0),
        "l_hip": (0, 0.5, 0), "r_hip": (0.2, 0.5, 0),
        "l_knee": (0, 0.9, 0), "r_knee": (0.2, 0.9, 0),
        "l_ankle": (0, 1.3, 0), "r_ankle": (0.2, 1.3, 0),
    }
    engine.world_scale = engine.set_scale(165, 150)
    measurements = engine.landmark_measurements(world)

    assert abs(measurements["shoulder_width"] - 44.0) < 1e-6
    assert abs(measurements["back_width"] - 46.64) < 1e-6
    assert measurements["blouse_length"] == measurements["half_length"]
    assert measurements["bustier_length"] > 0
    assert measurements["skirt_length"] > 0
