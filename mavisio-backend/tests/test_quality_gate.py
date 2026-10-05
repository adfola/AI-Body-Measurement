from app.core.quality_gate import check_capture


def make_landmarks(visibility=1.0, top=100, bottom=900):
    names = ["nose", "l_shoulder", "r_shoulder", "l_hip", "r_hip", "l_ankle", "r_ankle", "l_wrist", "r_wrist"]
    ys = {"nose": top, "l_shoulder": 250, "r_shoulder": 250, "l_hip": 500, "r_hip": 500, "l_ankle": bottom, "r_ankle": bottom, "l_wrist": 450, "r_wrist": 450}
    xs = {"l_shoulder": 400, "r_shoulder": 600, "l_wrist": 330, "r_wrist": 670}
    return {name: (xs.get(name, 500), ys[name], visibility) for name in names}


def test_good_front():
    assert check_capture(make_landmarks(), 1000, "front") == []


def test_hidden_body():
    assert "full_body_not_visible" in check_capture(make_landmarks(visibility=0.1), 1000, "front")


def test_too_far():
    assert "step_closer" in check_capture(make_landmarks(top=400, bottom=700), 1000, "front")
