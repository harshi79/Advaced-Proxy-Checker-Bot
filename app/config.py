from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


MAX_FILE_BYTES = 20 * 1024 * 1024


def _int(name: str, default: int, minimum: int = 0) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(value, minimum)


def _float(name: str, default: float, minimum: float = 0.1) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(value, minimum)


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    owner_id: int
    port: int
    render_external_url: str
    webhook_url: str
    webhook_secret: str
    check_url: str
    header_echo_url: str
    check_timeout_seconds: float
    check_retries: int
    check_concurrency: int
    progress_update_seconds: float
    worker_count: int
    data_dir: Path
    welcome_image: Path
    log_level: str
    max_file_bytes: int = MAX_FILE_BYTES

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("DATA_DIR", "data"))
        image_path = Path(os.getenv("WELCOME_IMAGE", "assets/welcome.png"))
        render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
        explicit_webhook = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
        return cls(
            bot_token=os.getenv("BOT_TOKEN", "").strip(),
            owner_id=_int("OWNER_ID", 7728424218, minimum=1),
            port=_int("PORT", 10000, minimum=1),
            render_external_url=render_url,
            webhook_url=explicit_webhook or render_url,
            webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip(),
            check_url=os.getenv("CHECK_URL", "https://api.ipify.org?format=json").strip(),
            header_echo_url=os.getenv("HEADER_ECHO_URL", "").strip(),
            check_timeout_seconds=_float("CHECK_TIMEOUT_SECONDS", 8.0, minimum=1.0),
            check_retries=_int("CHECK_RETRIES", 1, minimum=0),
            check_concurrency=_int("CHECK_CONCURRENCY", 100, minimum=1),
            progress_update_seconds=_float("PROGRESS_UPDATE_SECONDS", 1.2, minimum=0.5),
            worker_count=_int("WORKER_COUNT", 2, minimum=1),
            data_dir=data_dir,
            welcome_image=image_path,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    @property
    def telegram_webhook_url(self) -> str:
        if not self.webhook_url:
            return ""
        return f"{self.webhook_url}/telegram/webhook"

    def validate(self) -> None:
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN is required")
        if not self.check_url:
            raise RuntimeError("CHECK_URL must not be empty")
