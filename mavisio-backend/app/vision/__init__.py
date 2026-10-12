"""
Vision package — body detection, tracking, and geometry.

Components
----------
yolo_detector     : YOLO segmentation, fallback pose, custom keypoints
landmark_tracker  : Per-landmark Kalman-filtered tracker with confidence
camera_geometry   : Pixel ↔ cm conversion (ArUco + height-based)
segmentation      : BodySegmentation helper (mask utilities)
"""
from app.vision.yolo_detector import YoloSegmentor, CustomKeypointDetector
from app.vision.landmark_tracker import LandmarkTracker
from app.vision.camera_geometry import CameraGeometry

__all__ = [
    "YoloSegmentor",
    "CustomKeypointDetector",
    "LandmarkTracker",
    "CameraGeometry",
]

