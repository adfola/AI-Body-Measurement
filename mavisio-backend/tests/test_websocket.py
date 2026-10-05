import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.endpoints.stream import router

app = FastAPI()
app.include_router(router, prefix="/ws")


def test_rejects_bad_token():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/measurement") as socket:
            socket.send_json({"type": "auth", "token": "invalid"})
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()
