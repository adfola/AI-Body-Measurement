"""
Camera geometry: pixel ↔ real-world unit conversion.

This module solves one of the hardest problems in body measurement:
"200 pixels does not mean 200 cm."

Two complementary approaches are provided:

1. Height-based scale (fastest, works without physical markers)
   Use the person's known height to derive a cm-per-pixel ratio from the
   visible body height in the segmentation mask.

2. ArUco marker scale (most accurate, requires a printed marker)
   Detect a printed ArUco marker of known physical size and compute the
   exact pixel-per-cm ratio from its apparent size in the image.
   This is independent of the person's distance from the camera and
   handles slight perspective / tilt gracefully.

Both methods are encapsulated in CameraGeometry, which is the single source
of truth for unit conversion in the measurement engine.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# ArUco dictionary selection (OpenCV ≥ 4.7 uses the new API)
# ---------------------------------------------------------------------------
try:
    _ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    _ARUCO_PARAMS = cv2.aruco.DetectorParameters()
    _ARUCO_DETECTOR = cv2.aruco.ArucoDetector(_ARUCO_DICT, _ARUCO_PARAMS)
    _USE_NEW_ARUCO = True
except AttributeError:
    # OpenCV < 4.7 fallback
    _ARUCO_DICT = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
    _ARUCO_PARAMS = cv2.aruco.DetectorParameters_create()
    _ARUCO_DETECTOR = None
    _USE_NEW_ARUCO = False


@dataclass
class ScaleResult:
    """Result from a scale estimation method."""

    cm_per_px: float           # centimetres per pixel at the subject plane
    px_per_cm: float           # inverse
    source: str                # "aruco" | "height" | "combined"
    confidence: float          # 0–1, higher = more reliable
    marker_id: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_real_cm(self, pixels: float) -> float:
        return pixels * self.cm_per_px

    def to_pixels(self, cm: float) -> float:
        return cm * self.px_per_cm


class CameraGeometry:
    """
    Pixel ↔ centimetre conversion for body measurement.

    Intended use
    ------------
    geom = CameraGeometry()
    scale = geom.estimate_scale(frame, mask, known_height_cm=172.0,
                                body_top_px=50, body_bottom_px=680)
    waist_cm = scale.to_real_cm(waist_width_px)
    """

    # ------------------------------------------------------------------
    # ArUco detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_aruco(
        frame: np.ndarray,
        marker_real_cm: float = 10.0,
    ) -> ScaleResult | None:
        """
        Detect a single ArUco marker (DICT_4X4_50) in *frame* and return
        the scale based on its known physical side length *marker_real_cm*.

        The marker should be placed at the same depth plane as the body
        (e.g. taped to the floor in front of the person or held at waist height).

        Parameters
        ----------
        frame : BGR image (numpy array)
        marker_real_cm : physical side length of the printed marker in cm

        Returns
        -------
        ScaleResult or None if no marker found.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if _USE_NEW_ARUCO and _ARUCO_DETECTOR is not None:
            corners, ids, _ = _ARUCO_DETECTOR.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(gray, _ARUCO_DICT, parameters=_ARUCO_PARAMS)

        if ids is None or len(ids) == 0:
            return None

        # Use the first detected marker
        corner = corners[0].reshape(4, 2)
        marker_id = int(ids[0][0])

        # Compute apparent pixel side lengths (mean of 4 sides)
        sides_px = [
            math.dist(corner[i], corner[(i + 1) % 4])
            for i in range(4)
        ]
        mean_side_px = float(np.mean(sides_px))
        std_side_px = float(np.std(sides_px))

        if mean_side_px < 10:
            return None  # Marker too small — likely a false positive

        cm_per_px = marker_real_cm / mean_side_px
        px_per_cm = mean_side_px / marker_real_cm

        # Confidence: high when all 4 sides are consistent (low std)
        side_consistency = 1.0 - min(std_side_px / max(mean_side_px, 1), 1.0)
        confidence = 0.5 + 0.5 * side_consistency

        notes = []
        if std_side_px / mean_side_px > 0.1:
            notes.append("marker_tilted_perspective_correction_recommended")

        return ScaleResult(
            cm_per_px=cm_per_px,
            px_per_cm=px_per_cm,
            source="aruco",
            confidence=confidence,
            marker_id=marker_id,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Height-based scale
    # ------------------------------------------------------------------

    @staticmethod
    def scale_from_height(
        body_top_px: float,
        body_bottom_px: float,
        known_height_cm: float,
    ) -> ScaleResult | None:
        """
        Derive scale from the person's known height and their vertical extent
        in pixels (crown of head → heel).

        Parameters
        ----------
        body_top_px, body_bottom_px : pixel y-coordinates of head top and heel
        known_height_cm : verified height of the subject (no shoes)

        Returns
        -------
        ScaleResult or None if the inputs are implausible.
        """
        body_height_px = abs(body_bottom_px - body_top_px)
        if body_height_px < 50:
            return None  # Body not visible or too small

        cm_per_px = known_height_cm / body_height_px
        px_per_cm = body_height_px / known_height_cm

        # Confidence is lower than ArUco because it depends on pose quality
        confidence = 0.65

        return ScaleResult(
            cm_per_px=cm_per_px,
            px_per_cm=px_per_cm,
            source="height",
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Combined / preferred estimator
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_scale(
        frame: np.ndarray,
        known_height_cm: float,
        body_top_px: float,
        body_bottom_px: float,
        aruco_marker_cm: float = 10.0,
    ) -> ScaleResult | None:
        """
        Prefer ArUco when available, fall back to height-based scaling.

        This is the main entry point for the measurement pipeline.
        """
        aruco = CameraGeometry.detect_aruco(frame, aruco_marker_cm)
        height = CameraGeometry.scale_from_height(body_top_px, body_bottom_px, known_height_cm)

        if aruco and height:
            # Weighted combination — ArUco has higher confidence
            w_a, w_h = aruco.confidence, height.confidence
            total = w_a + w_h
            combined_cm_per_px = (aruco.cm_per_px * w_a + height.cm_per_px * w_h) / total
            combined_px_per_cm = 1.0 / combined_cm_per_px
            return ScaleResult(
                cm_per_px=combined_cm_per_px,
                px_per_cm=combined_px_per_cm,
                source="combined",
                confidence=min(aruco.confidence + 0.1, 1.0),
                marker_id=aruco.marker_id,
                notes=["aruco+height_fused"],
            )

        if aruco:
            return aruco

        if height:
            return height

        return None

    # ------------------------------------------------------------------
    # Distortion / lens correction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def undistort_frame(
        frame: np.ndarray,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
    ) -> np.ndarray:
        """Apply lens distortion correction using pre-computed intrinsics."""
        h, w = frame.shape[:2]
        new_mtx, roi = cv2.getOptimalNewCameraMatrix(
            camera_matrix, dist_coeffs, (w, h), 1, (w, h)
        )
        corrected = cv2.undistort(frame, camera_matrix, dist_coeffs, None, new_mtx)
        x, y, rw, rh = roi
        if rw > 0 and rh > 0:
            corrected = corrected[y : y + rh, x : x + rw]
        return corrected

    @staticmethod
    def calibrate_from_chessboard(
        images: list[np.ndarray],
        board_size: tuple[int, int] = (9, 6),
        square_size_cm: float = 2.5,
    ) -> tuple[np.ndarray, np.ndarray] | None:
        """
        Estimate camera intrinsics from a set of chessboard calibration images.

        Parameters
        ----------
        images : list of BGR frames containing the chessboard
        board_size : (cols, rows) of inner corners
        square_size_cm : physical square size in cm

        Returns
        -------
        (camera_matrix, dist_coeffs) or None if calibration fails.
        """
        objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0 : board_size[0], 0 : board_size[1]].T.reshape(-1, 2)
        objp *= square_size_cm

        obj_points: list[np.ndarray] = []
        img_points: list[np.ndarray] = []

        for img in images:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, board_size, None)
            if found:
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
                corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                obj_points.append(objp)
                img_points.append(corners_refined)

        if len(obj_points) < 5:
            return None  # Not enough valid calibration frames

        h, w = images[0].shape[:2]
        ret, mtx, dist, _, _ = cv2.calibrateCamera(obj_points, img_points, (w, h), None, None)
        if not ret:
            return None

        return mtx, dist
