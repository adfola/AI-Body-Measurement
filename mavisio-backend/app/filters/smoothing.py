import numpy as np


class TemporalSmoother:
    def __init__(self, window_size: int = 15):
        self.window_size = window_size
        self.history: list[dict[str, float]] = []

    def add(self, measurements: dict[str, float]) -> None:
        self.history = (self.history + [measurements])[-self.window_size:]

    def median_values(self) -> dict[str, float]:
        if not self.history:
            return {}
        keys = self.history[0].keys()
        return {
            key: float(np.median([sample[key] for sample in self.history]))
            for key in keys
        }
