import numpy as np


class LandmarkKalmanFilter:
    def __init__(self, process_noise: float = 1e-3, measurement_noise: float = 1e-1):
        self.q = process_noise
        self.r = measurement_noise
        self.x: np.ndarray | None = None
        self.p: np.ndarray | None = None

    def update(self, z: np.ndarray) -> np.ndarray:
        if self.x is None:
            self.x = z.astype(float)
            self.p = np.ones_like(z, dtype=float)
            return self.x
        p_prior = self.p + self.q
        gain = p_prior / (p_prior + self.r)
        self.x = self.x + gain * (z - self.x)
        self.p = (1 - gain) * p_prior
        return self.x
