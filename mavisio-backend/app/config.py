from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]
    model_complexity: int = 1
    yolo_weights: str = "yolo11n-pose.pt"
    calibration_samples: int = 40
    max_symmetry_error: float = 0.15
    max_frame_chars: int = 400_000
    db_pool_size: int = 10
    db_max_overflow: int = 20


settings = Settings()
