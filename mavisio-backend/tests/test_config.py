from app.config import Settings
from app.db.schemas import MeasurementOut


def test_render_postgres_url_uses_asyncpg_driver():
    settings = Settings(
        database_url="postgres://user:password@example.test/mavisio",
        jwt_secret="test-secret",
    )

    assert settings.database_url == "postgresql+asyncpg://user:password@example.test/mavisio"


def test_existing_asyncpg_url_is_preserved():
    database_url = "postgresql+asyncpg://user:password@example.test/mavisio"
    settings = Settings(database_url=database_url, jwt_secret="test-secret")

    assert settings.database_url == database_url


def test_measurement_response_keeps_centimeters_and_adds_inches():
    result = MeasurementOut(name="waist", value_cm=92.71).model_dump()

    assert result == {
        "name": "waist",
        "value_cm": 92.71,
        "value_inches": 36.5,
    }
