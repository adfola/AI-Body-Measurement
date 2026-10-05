import math
from collections.abc import Mapping, Sequence


class MetaPoseDetector:
    def __init__(self, max_symmetry_error: float = 0.15):
        self.max_err = max_symmetry_error

    def _pair(self, first: float, second: float) -> bool:
        average = (first + second) / 2
        return average > 0 and abs(first - second) / average <= self.max_err

    def validate(self, world: Mapping[str, Sequence[float]]) -> tuple[bool, str | None]:
        distance = math.dist
        if not self._pair(
            distance(world["l_shoulder"], world["l_elbow"]),
            distance(world["r_shoulder"], world["r_elbow"]),
        ):
            return False, "arm_asymmetry"
        if not self._pair(
            distance(world["l_hip"], world["l_knee"]),
            distance(world["r_hip"], world["r_knee"]),
        ):
            return False, "thigh_asymmetry"
        return True, None
