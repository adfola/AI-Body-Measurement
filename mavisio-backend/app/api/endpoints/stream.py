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
from app.core.meta_pose import MetaPoseDetector
from app.core.pose_detector import NAMES
from app.core.quality_gate import check_capture
from app.core.security import decode_token
from app.core.tailoring_engine import TailoringEngine
from app.db.models import Customer, MeasurementSession, TailoringMeasurement
from app.db.session import SessionLocal
from app.utils.image_decoder import decode_frame
from app.utils.logger import get_logger

router = APIRouter()
log = get_logger("stream")
KEYS = list(NAMES)


class MeasurementContext:
    def __init__(self, detector: Any, height_cm: float, view: str):
        self.detector = detector
        self.height_cm = height_cm
        self.view = view
        self.kalman = LandmarkKalmanFilter()
        self.engine = TailoringEngine()
        self.meta = MetaPoseDetector(settings.max_symmetry_error)
        self.calibrator = SampleCalibrator(settings.calibration_samples)
        self.correction_model = BodyShapeCorrectionModel()
        self.buffer: list[dict[str, float]] = []
        self.views: dict[str, dict[str, float]] = {}

    def set_view(self, view: str) -> None:
        if view not in {"front", "side"}:
            raise ValueError("view must be front or side")
        self.view = view
        self.buffer = []

    def process(self, frame: np.ndarray) -> dict[str, Any]:
        result = self.detector.process_frame(frame)
        if result is None or result["px"] is None:
            return {"status": "coaching", "coaching": ["full_body_not_visible"]}
        issues = check_capture(result["px"], frame.shape[0], self.view)
        if issues:
            if self.engine.world_scale is None:
                self.calibrator.reset()
            return {"status": "coaching", "coaching": issues}
        if self.view == "front":
            valid, reason = self.meta.validate(result["world"])
            if not valid:
                return {"status": "bad_pose", "reason": reason}

        vector = np.array([coordinate for key in KEYS for coordinate in result["world"][key]])
        smoothed = self.kalman.update(vector).reshape(-1, 3)
        world = {key: tuple(smoothed[index]) for index, key in enumerate(KEYS)}

        if self.engine.world_scale is None:
            complete = self.calibrator.add(self.engine.estimated_height_cm(world))
            if not complete:
                return {"status": "calibrating", "progress": len(self.calibrator.samples) / self.calibrator.n}
            self.engine.set_scale(self.height_cm, self.calibrator.result())
            if not self.engine.torso_is_plausible(world, self.height_cm):
                self.engine.world_scale = None
                self.calibrator.reset()
                return {"status": "recalibrate"}

        measurements = self.engine.measure(world)
        widths = circ.level_widths_cm(
            result["mask"],
            result["px"]["l_shoulder"][1],
            result["px"]["l_hip"][1],
            self.height_cm,
        )
        measurements.update({f"width_{name}": value for name, value in widths.items()})
        self.buffer = (self.buffer + [measurements])[-15:]
        return {
            "status": "ok",
            "calibrated": True,
            "view": self.view,
            "measurements": {
                name: round(value, 1)
                for name, value in measurements.items()
                if not name.startswith("width_")
            },
        }

    def lock_view(self) -> bool:
        if len(self.buffer) < 5:
            return False
        keys = self.buffer[0]
        self.views[self.view] = {
            key: float(np.median([sample[key] for sample in self.buffer])) for key in keys
        }
        return True

    def final(self) -> dict[str, float]:
        front = self.views.get("front")
        side = self.views.get("side")
        if not front or not side:
            raise ValueError("Capture both front and side views before saving")
        output = {key: value for key, value in front.items() if not key.startswith("width_")}
        
        front_widths = {
            key.replace("width_", ""): value for key, value in front.items() if key.startswith("width_")
        }
        side_depths = {
            key.replace("width_", ""): value for key, value in side.items() if key.startswith("width_")
        }

        output.update(circ.combine(front_widths, side_depths))

        corrected = self.correction_model.correct_all(
            measurements=output,
            height_cm=self.height_cm,
            front_widths=front_widths,
            side_depths=side_depths,
            scale_factor=self.engine.world_scale or 1.0,
        )

        return {name: round(value, 1) for name, value in corrected.items()}


async def _authenticate(ws: WebSocket) -> str | None:
    try:
        message = await asyncio.wait_for(ws.receive_json(), timeout=5)
        if message.get("type") != "auth":
            return None
        return decode_token(message["token"])
    except Exception:
        return None


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
                if view not in {"front", "side"}:
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
                log.info("frame processed in %.1f ms", (time.perf_counter() - started) * 1000)
                await ws.send_json(output)
            elif message_type == "capture" and context:
                await ws.send_json({
                    "status": "captured" if context.lock_view() else "not_ready",
                    "view": context.view,
                })
            elif message_type == "save" and context:
                final = context.final()
                async with SessionLocal() as db:
                    session = MeasurementSession(
                        customer_id=state["customer_id"],
                        scale_factor=context.engine.world_scale,
                    )
                    session.measurements = [
                        TailoringMeasurement(name=name, value_cm=value)
                        for name, value in final.items()
                    ]
                    db.add(session)
                    await db.commit()
                await ws.send_json({"status": "saved", "measurements": final})
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
