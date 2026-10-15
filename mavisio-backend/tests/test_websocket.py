import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.endpoints.stream import MeasurementContext, router

app = FastAPI()
app.include_router(router, prefix="/ws")


def test_rejects_bad_token():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/measurement") as socket:
            socket.send_json({"type": "auth", "token": "invalid"})
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()


def test_final_measurements_keep_back_width_offset_and_add_inches():
    context = MeasurementContext(detector=None, height_cm=165, view="front")
    context.engine.world_scale = 1.0
    context.views = {
        "front": {
            "measurements": {"shoulder_width": 30.0, "back_width": 31.8},
            "mask": None,
        },
        "back": {
            "measurements": {"shoulder_width": 32.0, "back_width": 33.92},
            "mask": None,
        },
    }

    result = context.final()

    assert result["measurements"]["back_width"] == 33.9
    assert result["measurements_inches"]["back_width"] == 13.3
