from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    firms_map_key: str = os.getenv("FIRMS_MAP_KEY", "").strip()
    frontend_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    )
    request_timeout_seconds: float = float(
        os.getenv("FIRMS_REQUEST_TIMEOUT_SECONDS", "45")
    )


settings = Settings()

