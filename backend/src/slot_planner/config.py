from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class configurations(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    anthropic_api_key: str
    anthropic_model: str = "claude-haiku-4-5-20251001"
    tud_base_url: str
    tud_api_key: str
    tud_model: str
    default_provider: Literal["anthropic", "tud"] = "tud"

settings = configurations()