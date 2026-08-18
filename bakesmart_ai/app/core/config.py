import os
from dataclasses import dataclass


def _origins_from_environment() -> tuple[str, ...]:
    raw_value = os.getenv(
        "BAKESMART_AI_ALLOWED_ORIGINS",
        "http://localhost,http://127.0.0.1",
    )
    origins = tuple(value.strip() for value in raw_value.split(",") if value.strip())
    return origins or ("http://localhost", "http://127.0.0.1")


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str = "BakeSmart AI"
    host: str = os.getenv("BAKESMART_AI_HOST", "0.0.0.0")
    port: int = int(os.getenv("BAKESMART_AI_PORT", "8000"))
    log_level: str = os.getenv("BAKESMART_AI_LOG_LEVEL", "INFO").upper()
    allowed_origins: tuple[str, ...] = _origins_from_environment()


settings = Settings()
