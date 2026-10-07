from ultralytics import YOLO


class YoloPoseDetector:
    def __init__(self, weights: str = "yolo11n-pose.pt"):
        self.model = YOLO(weights)

    def detect(self, frame):
        results = self.model(frame, verbose=False)
        return results[0] if results else None
