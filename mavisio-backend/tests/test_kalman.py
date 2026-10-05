import numpy as np

from app.core.kalman_filter import LandmarkKalmanFilter


def test_converges_and_reduces_noise():
    rng = np.random.default_rng(0)
    kalman = LandmarkKalmanFilter()
    outputs = [kalman.update(np.array([1.0]) + rng.normal(0, 0.1, 1))[0] for _ in range(200)]
    assert abs(np.mean(outputs[50:]) - 1.0) < 0.05
    assert np.std(outputs[50:]) < 0.1
