# pyrefly: ignore [missing-import]
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str
    jwt_secret: str
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    # MediaPipe
    model_complexity: int = 1

    # YOLO weights
    yolo_weights: str = "yolo11n-pose.pt"          # Pose fallback
    yolo_seg_weights: str = "yolo11n-seg.pt"        # Segmentation (body silhouette)
    custom_kp_weights: str = ""                      # Custom tailor keypoints (optional)

    # Calibration
    calibration_samples: int = 40
    max_symmetry_error: float = 0.15

    # ArUco marker physical size (cm) — printed marker used for scale reference
    aruco_marker_cm: float = 10.0

    # Frame limits
    max_frame_chars: int = 400_000

    # DB pool
    db_pool_size: int = 10
    db_max_overflow: int = 20

    @field_validator("database_url", mode="before")
    @classmethod
    def use_async_postgres_driver(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


settings = Settings()
