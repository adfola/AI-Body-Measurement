import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router, ws_router
from app.config import settings
from app.core.pose_detector import PoseDetector
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.detector = PoseDetector(settings.model_complexity, settings.yolo_weights)
    app.state.inference_lock = asyncio.Lock()
    yield
    app.state.detector.close()
    await engine.dispose()


app = FastAPI(title="Mavisio API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/ws")
