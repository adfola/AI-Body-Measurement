import math
from collections.abc import Mapping, Sequence

PAIRS = [("l_shoulder", "r_shoulder"), ("l_hip", "r_hip"), ("l_ankle", "r_ankle")]
FRONT_KEYS = ["nose", *(key for pair in PAIRS for key in pair)]


def check_capture(px: Mapping[str, Sequence[float]], frame_h: int, view: str) -> list[str]:
    issues = []
    if view == "front":
        visible = all(px[key][2] >= 0.5 for key in FRONT_KEYS)
        keys = FRONT_KEYS
    else:
        visible = px["nose"][2] >= 0.5 and all(
            max(px[first][2], px[second][2]) >= 0.5 for first, second in PAIRS
        )
        keys = ["nose", *(first for first, _ in PAIRS)]
    if not visible:
        issues.append("full_body_not_visible")
    ys = [px[key][1] for key in keys]
    fraction = (max(ys) - min(ys)) / max(frame_h, 1)
    if fraction < 0.6:
        issues.append("step_closer")
    if fraction > 0.92:
        issues.append("step_back")
    if min(ys) < 0.03 * frame_h or max(ys) > 0.97 * frame_h:
        issues.append("frame_cut_off")
    if view == "front":
        for side in ("l", "r"):
            dx = px[f"{side}_wrist"][0] - px[f"{side}_shoulder"][0]
            dy = px[f"{side}_wrist"][1] - px[f"{side}_shoulder"][1]
            angle = math.degrees(math.atan2(abs(dx), max(dy, 1e-6)))
            if not 15 <= angle <= 50:
                issues.append("adjust_arms")
    return sorted(set(issues))
