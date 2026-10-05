import numpy as np


class SampleCalibrator:
    def __init__(self, n: int = 40):
        self.n = n
        self.samples: list[float] = []

    def add(self, value: float) -> bool:
        self.samples.append(value)
        return len(self.samples) >= self.n

    def reset(self) -> None:
        self.samples.clear()

    def result(self) -> float:
        values = np.asarray(self.samples)
        median = np.median(values)
        mad = np.median(np.abs(values - median)) or 1e-6
        inliers = values[np.abs(values - median) < 2 * mad]
        return float(inliers.mean())
