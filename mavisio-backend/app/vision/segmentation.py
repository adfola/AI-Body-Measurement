import numpy as np
from app.core.circumference import mask_width_px, body_height_px


class BodySegmentation:
    @staticmethod
    def extract_width_px(mask: np.ndarray, row: int, thresh: float = 0.5) -> float:
        return mask_width_px(mask, row, thresh)

    @staticmethod
    def extract_height_px(mask: np.ndarray, thresh: float = 0.5) -> float:
        return body_height_px(mask, thresh)
