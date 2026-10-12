"""
WebSocket streaming endpoint — real-time body measurement pipeline.

Frame processing pipeline (correct order per architecture recommendation)
-------------------------------------------------------------------------
    Camera frame (BGR, base64)
        ↓
    PoseDetector.process_frame()
        → MediaPipe landmarks + confidences
        → YOLO segmentation mask (sharper silhouette)
        → Custom YOLO tailor keypoints
        ↓
    Quality gate (check_capture)
        ↓
    LandmarkKalmanFilter  [LANDMARKS are smoothed, not measurements]
        ↓
    CameraGeometry.estimate_scale()  (height-based + ArUco if available)
        ↓
    MeasurementEngine.landmark_measurements()
        ↓  (buffered 1–3 seconds)
    MedianAggregation
        ↓
    MeasurementEngine.circumference_measurements()  (front + side masks)
        ↓
    BodyShapeCorrectionModel.correct_all()
        ↓
    Confidence scoring
        ↓
    JSON response → frontend

Message protocol
----------------
Client → Server (JSON):
    {type: "auth", token: <JWT>}
    {type: "start", customer_id: <uuid>, height_cm: <float>, view: "front"|"side"|"back"}
    {type: "image", data: <base64>}
    {type: "capture"}          — lock current view measurements
    {type: "save"}             — combine views & persist to DB

Server → Client (JSON):
    {status: "started", view: <str>}
    {status: "coaching", coaching: [<issue_codes>]}
    {status: "bad_pose", reason: <str>}
    {status: "calibrating", progress: <0–1>}
    {status: "recalibrate"}
    {status: "ok", calibrated: true, view: <str>, measurements: {...}, confidence: {...}}
    {status: "captured", view: <str>}
    {status: "not_ready"}
    {status: "saved", measurements: {...}, confidence: {...}}
    {status: "error", reason: <str>}
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.core import circumference as circ
from app.core.calibration import SampleCalibrator
from app.core.correction_model import BodyShapeCorrectionModel
from app.core.kalman_filter import LandmarkKalmanFilter
from app.core.measurement_engine import MeasurementEngine
from app.core.meta_pose import MetaPoseDetector
from app.core.pose_detector import NAMES
from app.core.quality_gate import check_capture
from app.core.security import decode_token
from app.db.models import Customer, MeasurementSession, TailoringMeasurement
from app.db.session import SessionLocal
from app.utils.image_decoder import decode_frame
from app.utils.logger import get_logger
from app.vision.camera_geometry import CameraGeometry

router = APIRouter()
log = get_logger("stream")
KEYS = list(NAMES)


# ---------------------------------------------------------------------------
# Per-session measurement context
# ---------------------------------------------------------------------------


class MeasurementContext:
    """
    Holds all state for one WebSocket measurement session.

    A single session handles multiple views (front, side, back) sequentially.
    The Kalman filter is reset between views to prevent cross-contamination.
    """

    def __init__(self, detector: Any, height_cm: float, view: str):
        self.detector = detector
        self.height_cm = height_cm
        self.view = view

        # Kalman filter: smooths flat landmark vector (backward-compatible)
        self.kalman = LandmarkKalmanFilter()

        # Measurement engine (replaces TailoringEngine)
        self.engine = MeasurementEngine()

        # Legacy objects kept for pose validation
        self.meta = MetaPoseDetector(settings.max_symmetry_error)

        # Calibrator: collects world-landmark height samples to derive scale
        self.calibrator = SampleCalibrator(settings.calibration_samples)

        # Correction model
        self.correction_model = BodyShapeCorrectionModel()

        # Camera geometry helper (ArUco + height-based)
        self.geometry = CameraGeometry()

        # Rolling buffer of measurements (last 15 frames per view)
        self.buffer: list[dict[str, float]] = []

        # Width buffers per view for circumference averaging
        self.mask_buffer: list[np.ndarray] = []

        # Per-view locked snapshots: {view_name: {"measurements": ..., "mask": ...}}
        self.views: dict[str, dict[str, Any]] = {}

        # Latest scale result from camera geometry
        self._scale_cm_per_px: float | None = None

    # ------------------------------------------------------------------
    # View management
    # ------------------------------------------------------------------

    def set_view(self, view: str) -> None:
        if view not in {"front", "side", "back"}:
            raise ValueError("view must be front, side, or back")
        self.view = view
        self.buffer = []
        self.mask_buffer = []
        # Reset Kalman so pose jitter from the previous angle doesn't bleed in
        self.kalman.reset()

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process(self, frame: np.ndarray) -> dict[str, Any]:
        """
        Process one frame through the full pipeline.

        Returns a JSON-serialisable status dict.
        """
        result = self.detector.process_frame(frame)
        if result is None or result.get("px") is None:
            return {"status": "coaching", "coaching": ["full_body_not_visible"]}

        # ---- Quality gate ----
        issues = check_capture(result["px"], frame.shape[0], self.view)
        if issues:
            if self.engine.world_scale is None:
                self.calibrator.reset()
            return {"status": "coaching", "coaching": issues}

        # ---- Pose symmetry check (front view only) ----
        if self.view == "front":
            valid, reason = self.meta.validate(result["world"])
            if not valid:
                return {"status": "bad_pose", "reason": reason}

        # ---- Step 1: Kalman smoothing on landmark coordinates ----
        # (Smooth raw landmarks BEFORE computing measurements)
        vector = np.array([
            coord
            for key in KEYS
            for coord in result["world"][key]
        ])
        smoothed = self.kalman.update(vector).reshape(-1, 3)
        world: dict[str, tuple[float, ...]] = {
            key: tuple(smoothed[i].tolist())
            for i, key in enumerate(KEYS)
        }

        # ---- Step 2: Scale calibration ----
        if self.engine.world_scale is None:
            est_h = MeasurementEngine.estimated_body_height_cm(world)
            complete = self.calibrator.add(est_h)
            if not complete:
                return {
                    "status": "calibrating",
                    "progress": len(self.calibrator.samples) / self.calibrator.n,
                }
            self.engine.set_scale(self.height_cm, self.calibrator.result())
            if not self.engine.torso_is_plausible(world, self.height_cm):
                self.engine.world_scale = None
                self.calibrator.reset()
                return {"status": "recalibrate"}

        # ---- Step 3: Camera geometry scale (from ArUco + height) ----
        mask = result.get("mask")
        if mask is not None:
            top_px, bot_px = circ.body_top_bottom_px(mask)
            scale_res = self.geometry.estimate_scale(
                frame=frame,
                known_height_cm=self.height_cm,
                body_top_px=top_px,
                body_bottom_px=bot_px,
            )
            if scale_res is not None:
                self._scale_cm_per_px = scale_res.cm_per_px

        # ---- Step 4: Landmark measurements from smoothed world coords ----
        cm_per_px = self._scale_cm_per_px
        custom_kp = result.get("custom_kp", {})

        measurements = self.engine.landmark_measurements(
            world=world,
            custom_px=custom_kp if custom_kp else None,
            cm_per_px=cm_per_px,
        )

        # ---- Step 5: Mask-based width extraction ----
        if mask is not None and cm_per_px:
            sh_y = result["px"]["l_shoulder"][1]
            hip_y = result["px"]["l_hip"][1]
            widths = circ.level_widths_cm_from_scale(mask, sh_y, hip_y, cm_per_px)
        elif mask is not None:
            sh_y = result["px"]["l_shoulder"][1]
            hip_y = result["px"]["l_hip"][1]
            widths = circ.level_widths_cm(mask, sh_y, hip_y, self.height_cm)
        else:
            widths = {}

        # Store widths with a prefix so they don't pollute measurement output
        for name, val in widths.items():
            measurements[f"_width_{name}"] = val

        # Buffer mask for later circumference calculation
        if mask is not None:
            self.mask_buffer = (self.mask_buffer + [mask])[-15:]

        # Buffer measurements
        self.buffer = (self.buffer + [measurements])[-15:]

        # ---- Step 6: Confidence scoring ----
        frame_conf = result.get("frame_conf", 0.8)
        confidence = MeasurementEngine.confidence_scores(
            measurements={k: v for k, v in measurements.items() if not k.startswith("_")},
            world_scale=self.engine.world_scale,
            frame_conf=frame_conf,
            has_segmentation=mask is not None,
            has_side_view="side" in self.views,
            has_custom_keypoints=bool(custom_kp),
        )

        return {
            "status": "ok",
            "calibrated": True,
            "view": self.view,
            "measurements": {
                name: round(value, 1)
                for name, value in measurements.items()
                if not name.startswith("_")
            },
            "confidence": confidence,
            "source": result.get("source", "mediapipe"),
        }

    # ------------------------------------------------------------------
    # View locking (captures median of buffered frames)
    # ------------------------------------------------------------------

    def lock_view(self) -> bool:
        """Lock the current view by taking the median of the frame buffer."""
        if len(self.buffer) < 5:
            return False

        keys = self.buffer[0].keys()
        locked = {
            key: float(np.median([sample[key] for sample in self.buffer]))
            for key in keys
        }

        # Best mask: mean of buffered masks for circumference calculation
        best_mask: np.ndarray | None = None
        if self.mask_buffer:
            best_mask = np.mean(self.mask_buffer, axis=0)

        self.views[self.view] = {
            "measurements": locked,
            "mask": best_mask,
        }
        return True

    # ------------------------------------------------------------------
    # Final combined result
    # ------------------------------------------------------------------

    def final(self) -> dict[str, Any]:
        """
        Combine all captured views into final measurements + confidence.

        Requires at least front view.  Side view adds circumference depth.
        Back view refines back_width if captured.
        """
        front_data = self.views.get("front")
        if not front_data:
            raise ValueError("Capture front view before saving")

        front_meas = front_data["measurements"]
        front_mask = front_data.get("mask")
        side_data = self.views.get("side")
        back_data = self.views.get("back")

        # ---- Base: landmark measurements from front view ----
        output: dict[str, float] = {
            key: value
            for key, value in front_meas.items()
            if not key.startswith("_")
        }

        # ---- Circumferences: front + side masks ----
        if side_data and front_mask is not None and side_data.get("mask") is not None:
            side_mask = side_data["mask"]
            sh_y = 0.0  # We stored shoulder y in measurements via _width keys
            hip_y = 0.0

            front_widths = {
                k.replace("_width_", ""): v
                for k, v in front_meas.items()
                if k.startswith("_width_")
            }
            side_meas = side_data["measurements"]
            side_widths = {
                k.replace("_width_", ""): v
                for k, v in side_meas.items()
                if k.startswith("_width_")
            }

            circumferences = circ.combine(front_widths, side_widths)
            output.update(circumferences)

        elif front_mask is not None:
            # Front only: use fixed depth/width ratio (less accurate)
            front_widths = {
                k.replace("_width_", ""): v
                for k, v in front_meas.items()
                if k.startswith("_width_")
            }
            # Assume depth ≈ 60% of width (average body proportion)
            for level, w in front_widths.items():
                output[level] = circ.ramanujan_perimeter(w, w * 0.60)

        # ---- Back view refinement ----
        if back_data:
            back_meas = back_data["measurements"]
            if "shoulder_width" in back_meas:
                output["back_width"] = back_meas["shoulder_width"]

        # ---- Correction model ----
        front_widths_for_correction = {
            k.replace("_width_", ""): v
            for k, v in front_meas.items()
            if k.startswith("_width_")
        }
        side_meas_all = side_data["measurements"] if side_data else {}
        side_depths_for_correction = {
            k.replace("_width_", ""): v
            for k, v in side_meas_all.items()
            if k.startswith("_width_")
        }

        corrected = self.correction_model.correct_all(
            measurements=output,
            height_cm=self.height_cm,
            front_widths=front_widths_for_correction,
            side_depths=side_depths_for_correction,
            scale_factor=self.engine.world_scale or 1.0,
        )

        # ---- Final confidence ----
        confidence = MeasurementEngine.confidence_scores(
            measurements=corrected,
            world_scale=self.engine.world_scale,
            frame_conf=0.85,  # At lock-time we already passed quality gate
            has_segmentation=front_mask is not None,
            has_side_view=side_data is not None,
            has_custom_keypoints=False,
        )

        final_measurements = {name: round(value, 1) for name, value in corrected.items()}
        return {
            "measurements": final_measurements,
            "confidence": confidence,
        }


# ---------------------------------------------------------------------------
# WebSocket authentication helper
# ---------------------------------------------------------------------------


async def _authenticate(ws: WebSocket) -> str | None:
    try:
        message = await asyncio.wait_for(ws.receive_json(), timeout=5)
        if message.get("type") != "auth":
            return None
        return decode_token(message["token"])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main WebSocket handler
# ---------------------------------------------------------------------------


@router.websocket("/measurement")
async def measurement(ws: WebSocket):
    await ws.accept()
    user_id = await _authenticate(ws)
    if not user_id:
        await ws.close(code=1008)
        return

    controls: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    frame_ready = asyncio.Event()
    latest_frame: dict[str, Any] | None = None
    state: dict[str, Any] = {"context": None, "customer_id": None}

    async def reader() -> None:
        nonlocal latest_frame
        while True:
            message = await ws.receive_json()
            if message.get("type") == "image":
                latest_frame = message
            else:
                await controls.put(message)
            frame_ready.set()

    async def process_message(message: dict[str, Any]) -> None:
        nonlocal latest_frame
        message_type = message.get("type")
        context: MeasurementContext | None = state["context"]
        try:
            if message_type == "start":
                customer_id = uuid.UUID(message["customer_id"])
                async with SessionLocal() as db:
                    customer = await db.get(Customer, customer_id)
                if not customer or str(customer.owner_id) != user_id:
                    await ws.send_json({"status": "error", "reason": "customer_not_found"})
                    return
                height = float(message.get("height_cm") or customer.height_cm or 0)
                if not 100 <= height <= 230:
                    await ws.send_json({"status": "error", "reason": "invalid_height"})
                    return
                view = message.get("view", "front")
                if view not in {"front", "side", "back"}:
                    await ws.send_json({"status": "error", "reason": "invalid_view"})
                    return
                state["customer_id"] = customer.id
                if context is None:
                    state["context"] = MeasurementContext(ws.app.state.detector, height, view)
                else:
                    context.set_view(view)
                await ws.send_json({"status": "started", "view": view})

            elif message_type == "image" and context:
                encoded = message.get("data", "")
                if len(encoded) > settings.max_frame_chars:
                    await ws.send_json({"status": "error", "reason": "frame_too_large"})
                    return
                frame = decode_frame(encoded)
                started = time.perf_counter()
                async with ws.app.state.inference_lock:
                    output = await run_in_threadpool(context.process, frame)
                elapsed_ms = (time.perf_counter() - started) * 1000
                log.info("frame processed in %.1f ms | view=%s | source=%s",
                         elapsed_ms, context.view, output.get("source", "?"))
                await ws.send_json(output)

            elif message_type == "capture" and context:
                locked = context.lock_view()
                await ws.send_json({
                    "status": "captured" if locked else "not_ready",
                    "view": context.view,
                })

            elif message_type == "save" and context:
                result = context.final()
                final_measurements = result["measurements"]
                final_confidence = result["confidence"]
                async with SessionLocal() as db:
                    session = MeasurementSession(
                        customer_id=state["customer_id"],
                        scale_factor=context.engine.world_scale,
                    )
                    session.measurements = [
                        TailoringMeasurement(name=name, value_cm=value)
                        for name, value in final_measurements.items()
                    ]
                    db.add(session)
                    await db.commit()
                await ws.send_json({
                    "status": "saved",
                    "measurements": final_measurements,
                    "confidence": final_confidence,
                    "views_captured": list(context.views.keys()),
                })

        except (ValueError, KeyError, TypeError) as error:
            log.warning("Rejected malformed WebSocket message: %s", error)
            await ws.send_json({"status": "error", "reason": "bad_message"})

    async def worker() -> None:
        nonlocal latest_frame
        while True:
            await frame_ready.wait()
            frame_ready.clear()
            while not controls.empty():
                await process_message(controls.get_nowait())
            if latest_frame is not None:
                message, latest_frame = latest_frame, None
                await process_message(message)
            if not controls.empty() or latest_frame is not None:
                frame_ready.set()

    tasks = [asyncio.create_task(reader()), asyncio.create_task(worker())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            if not task.cancelled() and task.exception():
                raise task.exception()
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
