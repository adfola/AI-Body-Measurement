import math
from collections.abc import Mapping, Sequence

NOSE_TO_CROWN_CM = 11.5


class TailoringEngine:
    def __init__(self):
        self.world_scale: float | None = None

    @staticmethod
    def estimated_height_cm(world: Mapping[str, Sequence[float]]) -> float:
        heel_y = (world["l_heel"][1] + world["r_heel"][1]) / 2
        return abs(world["nose"][1] - heel_y) * 100 + NOSE_TO_CROWN_CM

    def set_scale(self, known_height_cm: float, estimated_height_cm: float) -> float:
        if estimated_height_cm <= 0:
            raise ValueError("Cannot estimate height")
        self.world_scale = known_height_cm / estimated_height_cm
        return self.world_scale

    def torso_is_plausible(
        self, world: Mapping[str, Sequence[float]], known_height_cm: float
    ) -> bool:
        torso = math.dist(world["l_shoulder"], world["l_hip"]) * 100 * (self.world_scale or 1.0)
        return 0.22 <= torso / known_height_cm <= 0.38

    def measure(self, world: Mapping[str, Sequence[float]]) -> dict[str, float]:
        scale = self.world_scale or 1.0

        def distance(first: str, second: str) -> float:
            return math.dist(world[first], world[second]) * 100 * scale

        return {
            "shoulder_width": distance("l_shoulder", "r_shoulder"),
            "sleeve": distance("l_shoulder", "l_elbow") + distance("l_elbow", "l_wrist"),
            "torso": distance("l_shoulder", "l_hip"),
            "inseam": distance("l_hip", "l_knee") + distance("l_knee", "l_ankle"),
        }
