from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py lives in backend/src/slot_planner/, so backend/ is three levels up
BACKEND_DIR = Path(__file__).resolve().parents[2]


class configurations(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")
    anthropic_api_key: str
    anthropic_model: str = "claude-haiku-4-5-20251001"
    tud_base_url: str
    tud_api_key: str
    tud_model: str
    default_provider: Literal["anthropic", "tud"] = "tud"


settings = configurations()
