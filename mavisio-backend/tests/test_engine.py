from app.core.tailoring_engine import TailoringEngine


def test_scale_and_shoulder_width():
    engine = TailoringEngine()
    assert abs(engine.set_scale(165, 150) - 1.1) < 1e-9
    world = {
        "l_shoulder": (0, 0, 0), "r_shoulder": (0.4, 0, 0),
        "l_elbow": (0, 0.3, 0), "l_wrist": (0, 0.55, 0),
        "l_hip": (0, 0.5, 0), "l_knee": (0, 0.9, 0), "l_ankle": (0, 1.3, 0),
    }
    assert abs(engine.measure(world)["shoulder_width"] - 44.0) < 1e-6
