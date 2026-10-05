from fastapi import APIRouter

from app.api.endpoints import auth, customers, health, measurements, stream

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(measurements.router, prefix="/measurements", tags=["measurements"])

ws_router = APIRouter()
ws_router.include_router(stream.router)
