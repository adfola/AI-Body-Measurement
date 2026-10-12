"""
YOLO segmentation + pose detector.

Responsibilities
----------------
- Run YOLO segmentation to obtain the person's body *silhouette mask*.
  This mask is used by the circumference engine for body-width extraction.
- Run YOLO pose estimation as a *fallback* when MediaPipe fails.
- Run a custom YOLO keypoint model for tailor-specific landmarks that
  MediaPipe does not reliably provide (e.g. waist boundary, under-bust).

Architecture note
-----------------
Do NOT use YOLO as the primary pose source.  MediaPipe Pose provides
more stable 3D world landmarks for the standard anatomical joints.
YOLO segmentation is best for the body silhouette / contour.
Custom YOLO keypoints add tailor-specific points on top of MediaPipe.

Model loading is lazy (first use) to keep startup time fast.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    from ultralytics import YOLO

    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


@dataclass
class SegmentationResult:
    """Output of YOLO segmentation on a single frame."""

    mask: np.ndarray | None      # H×W binary float32 mask (0–1) of the person
    bbox: tuple[int, int, int, int] | None  # (x1, y1, x2, y2) person bounding box
    confidence: float = 0.0


@dataclass
class YoloPoseResult:
    """Output of YOLO pose estimation (fallback mode)."""

    keypoints_xy: np.ndarray | None   # shape (17, 2) COCO keypoints
    keypoints_conf: np.ndarray | None # shape (17,)
    bbox: tuple[int, int, int, int] | None


@dataclass
class CustomKeypointResult:
    """Output of a custom YOLO tailor-keypoint model."""

    # Keypoint name → (x_px, y_px, confidence)
    points: dict[str, tuple[float, float, float]]


class YoloSegmentor:
    """
    YOLO segmentation wrapper.

    Uses the best available YOLO segmentation model to extract the person
    silhouette.  The resulting binary mask replaces / augments the softer
    MediaPipe segmentation mask for contour-based width extraction.

    Parameters
    ----------
    seg_weights : str
        Path or name of the YOLO segmentation model (e.g. ``yolo11n-seg.pt``).
    conf_threshold : float
        Minimum detection confidence to accept a person.
    iou_threshold : float
        NMS IoU threshold.
    """

    # Standard COCO pose keypoint indices used as fallback
    COCO_KP_NAMES = [
        "nose", "l_eye", "r_eye", "l_ear", "r_ear",
        "l_shoulder", "r_shoulder",
        "l_elbow", "r_elbow",
        "l_wrist", "r_wrist",
        "l_hip", "r_hip",
        "l_knee", "r_knee",
        "l_ankle", "r_ankle",
    ]

    def __init__(
        self,
        seg_weights: str = "yolo11n-seg.pt",
        pose_weights: str = "yolo11n-pose.pt",
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
    ):
        if not _YOLO_AVAILABLE:
            raise ImportError("ultralytics is not installed. Run: pip install ultralytics")
        self.seg_weights = seg_weights
        self.pose_weights = pose_weights
        self.conf = conf_threshold
        self.iou = iou_threshold
        self._seg_model: Any | None = None
        self._pose_model: Any | None = None

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _load_seg(self) -> Any:
        if self._seg_model is None:
            self._seg_model = YOLO(self.seg_weights)
        return self._seg_model

    def _load_pose(self) -> Any:
        if self._pose_model is None:
            self._pose_model = YOLO(self.pose_weights)
        return self._pose_model

    # ------------------------------------------------------------------
    # Segmentation
    # ------------------------------------------------------------------

    def segment_person(self, frame: np.ndarray) -> SegmentationResult:
        """
        Extract a per-pixel body mask for the largest/most-confident person.

        Returns a SegmentationResult.  ``mask`` is None when no person is found.
        """
        model = self._load_seg()
        h, w = frame.shape[:2]
        results = model(frame, conf=self.conf, iou=self.iou, classes=[0], verbose=False)
        if not results:
            return SegmentationResult(mask=None, bbox=None)

        res = results[0]
        if res.masks is None or len(res.masks.data) == 0:
            return SegmentationResult(mask=None, bbox=None)

        # Pick the detection with highest confidence
        conf_scores = res.boxes.conf.cpu().numpy() if res.boxes is not None else np.array([0.0])
        best = int(np.argmax(conf_scores))
        best_conf = float(conf_scores[best])

        # Resize mask to frame dimensions
        raw_mask = res.masks.data[best].cpu().numpy()  # model-resolution mask
        mask_resized = _resize_mask(raw_mask, h, w)

        # Bounding box
        bbox: tuple[int, int, int, int] | None = None
        if res.boxes is not None and len(res.boxes.xyxy) > best:
            x1, y1, x2, y2 = res.boxes.xyxy[best].cpu().numpy().astype(int)
            bbox = (int(x1), int(y1), int(x2), int(y2))

        return SegmentationResult(mask=mask_resized, bbox=bbox, confidence=best_conf)

    # ------------------------------------------------------------------
    # Fallback pose estimation (when MediaPipe fails)
    # ------------------------------------------------------------------

    def fallback_pose(self, frame: np.ndarray) -> YoloPoseResult:
        """
        Run YOLO pose estimation as a fallback for MediaPipe.

        Returns COCO 17-keypoint results for the most confident person.
        """
        model = self._load_pose()
        results = model(frame, conf=self.conf, iou=self.iou, verbose=False)
        if not results:
            return YoloPoseResult(None, None, None)

        res = results[0]
        if res.keypoints is None or len(res.keypoints.xy) == 0:
            return YoloPoseResult(None, None, None)

        conf_scores = res.boxes.conf.cpu().numpy() if res.boxes is not None else np.array([0.0])
        best = int(np.argmax(conf_scores))

        kp_xy = res.keypoints.xy[best].cpu().numpy()   # (17, 2)
        kp_conf = (
            res.keypoints.conf[best].cpu().numpy()
            if res.keypoints.conf is not None
            else np.ones(17, dtype=float)
        )

        bbox: tuple[int, int, int, int] | None = None
        if res.boxes is not None and len(res.boxes.xyxy) > best:
            x1, y1, x2, y2 = res.boxes.xyxy[best].cpu().numpy().astype(int)
            bbox = (int(x1), int(y1), int(x2), int(y2))

        return YoloPoseResult(
            keypoints_xy=kp_xy,
            keypoints_conf=kp_conf,
            bbox=bbox,
        )

    def coco_to_mediapipe_format(
        self, pose: YoloPoseResult
    ) -> dict[str, tuple[float, float, float]] | None:
        """
        Convert COCO 17-keypoint pose to the name→(x, y, conf) dict format
        used by the rest of the pipeline.

        Only maps the subset of keypoints that share names with MediaPipe.
        """
        if pose.keypoints_xy is None:
            return None

        out: dict[str, tuple[float, float, float]] = {}
        for idx, name in enumerate(self.COCO_KP_NAMES):
            x, y = float(pose.keypoints_xy[idx, 0]), float(pose.keypoints_xy[idx, 1])
            conf = float(pose.keypoints_conf[idx]) if pose.keypoints_conf is not None else 0.5
            out[name] = (x, y, conf)
        return out


class CustomKeypointDetector:
    """
    Custom YOLO model for tailor-specific keypoints.

    These are landmarks that standard MediaPipe Pose does not reliably provide
    but that a tailor needs:

    - left_armpit / right_armpit
    - bust_left / bust_right        (bust-line outer boundary)
    - underbust_left / underbust_right
    - waist_left / waist_right
    - hip_left / hip_right

    The model must be trained on a custom annotated dataset.  Until a trained
    model is available, this class can be used in *anatomy-approximate* mode,
    which interpolates these points from MediaPipe's standard landmarks.

    Parameters
    ----------
    weights_path : str | None
        Path to a trained custom YOLO pose model.  If None or the file does
        not exist, falls back to anatomy-approximate mode.
    """

    # Anatomy-based interpolation coefficients:
    # Each point defined as a weighted sum of two MediaPipe landmarks.
    # Format: { target_name: (lm_a, lm_b, alpha) }
    # where point = lm_a * alpha + lm_b * (1 - alpha)
    _ANATOMY_APPROX: dict[str, tuple[str, str, float]] = {
        "l_armpit":       ("l_shoulder", "l_hip",      0.85),
        "r_armpit":       ("r_shoulder", "r_hip",      0.85),
        "bust_left":      ("l_shoulder", "l_hip",      0.70),
        "bust_right":     ("r_shoulder", "r_hip",      0.70),
        "underbust_left":  ("l_shoulder", "l_hip",     0.55),
        "underbust_right": ("r_shoulder", "r_hip",     0.55),
        "waist_left":     ("l_shoulder", "l_hip",      0.38),
        "waist_right":    ("r_shoulder", "r_hip",      0.38),
        "hip_left":       ("l_hip",      "l_knee",     0.90),
        "hip_right":      ("r_hip",      "r_knee",     0.90),
        "l_sleeve_end":   ("l_wrist",    "l_elbow",    1.10),  # slightly past wrist
        "r_sleeve_end":   ("r_wrist",    "r_elbow",    1.10),
    }

    def __init__(self, weights_path: str | None = None):
        self.weights_path = weights_path
        self._model: Any | None = None
        self._use_model = False

        if weights_path and Path(weights_path).exists() and _YOLO_AVAILABLE:
            try:
                self._model = YOLO(weights_path)
                self._use_model = True
            except Exception:
                self._use_model = False

    def detect(
        self,
        frame: np.ndarray,
        mediapipe_px: dict[str, tuple[float, float, float]],
    ) -> CustomKeypointResult:
        """
        Detect custom tailor keypoints.

        If a trained model is loaded, runs inference.  Otherwise, falls back
        to anatomy-based interpolation from MediaPipe landmarks.

        Parameters
        ----------
        frame : BGR image array
        mediapipe_px : MediaPipe px landmark dict {name: (x, y, conf)}

        Returns
        -------
        CustomKeypointResult with all tailor-specific points.
        """
        if self._use_model and self._model is not None:
            return self._model_detect(frame)
        return self._anatomy_approximate(mediapipe_px)

    def _model_detect(self, frame: np.ndarray) -> CustomKeypointResult:
        results = self._model(frame, verbose=False)
        if not results or results[0].keypoints is None:
            return CustomKeypointResult({})

        res = results[0]
        kp_xy = res.keypoints.xy[0].cpu().numpy()
        kp_conf = (
            res.keypoints.conf[0].cpu().numpy()
            if res.keypoints.conf is not None
            else np.ones(len(kp_xy))
        )

        point_names = list(self._ANATOMY_APPROX.keys())
        points: dict[str, tuple[float, float, float]] = {}
        for i, name in enumerate(point_names):
            if i < len(kp_xy):
                x, y = float(kp_xy[i, 0]), float(kp_xy[i, 1])
                conf = float(kp_conf[i]) if i < len(kp_conf) else 0.5
                points[name] = (x, y, conf)

        return CustomKeypointResult(points)

    def _anatomy_approximate(
        self,
        mediapipe_px: dict[str, tuple[float, float, float]],
    ) -> CustomKeypointResult:
        """
        Interpolate tailor-specific keypoints from known MediaPipe landmarks.

        Confidence is set to 0.5 to indicate these are approximations.
        The correction model downstream should handle the residual error.
        """
        points: dict[str, tuple[float, float, float]] = {}
        for name, (lm_a, lm_b, alpha) in self._ANATOMY_APPROX.items():
            if lm_a in mediapipe_px and lm_b in mediapipe_px:
                xa, ya, ca = mediapipe_px[lm_a]
                xb, yb, cb = mediapipe_px[lm_b]
                x = xa * alpha + xb * (1 - alpha)
                y = ya * alpha + yb * (1 - alpha)
                conf = min(ca, cb) * 0.5  # Lower confidence for approximations
                points[name] = (x, y, conf)
        return CustomKeypointResult(points)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resize_mask(mask: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Resize a YOLO-output mask to the original frame dimensions."""
    import cv2 as _cv2

    if mask.shape == (target_h, target_w):
        return mask.astype(np.float32)
    resized = _cv2.resize(mask, (target_w, target_h), interpolation=_cv2.INTER_LINEAR)
    return resized.astype(np.float32)
