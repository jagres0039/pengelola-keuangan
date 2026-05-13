"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: str = Field(
        default="",
        description="Token bot dari @BotFather.",
    )
    database_url: str = Field(
        default="sqlite:///./data/pengelola_keuangan.db",
        description="SQLAlchemy database URL.",
    )
    default_timezone: str = Field(
        default="Asia/Jakarta",
        description="IANA timezone untuk user baru.",
    )
    default_currency: str = Field(
        default="IDR",
        description="Currency code (ISO 4217) untuk user baru.",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level.",
    )
    allowed_user_ids: str = Field(
        default="",
        description="Comma-separated telegram_user_id yang boleh akses bot.",
    )
    gemini_api_key: str = Field(
        default="",
        description=(
            "API key Google AI Studio (Gemini) untuk OCR struk. "
            "Kosongin = fitur OCR struk dimatiin."
        ),
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model yang dipakai buat OCR struk.",
    )
    jwt_secret: str = Field(
        default="change-me-please-this-is-not-secure",
        description=(
            "Secret untuk sign JWT access token. WAJIB di-set di production "
            "(minimal 32 char random). Default cuma buat dev."
        ),
    )
    jwt_expires_minutes: int = Field(
        default=60 * 24 * 30,
        description="Durasi JWT access token (menit). Default 30 hari.",
    )
    cors_allow_origins: str = Field(
        default="*",
        description=(
            "Daftar origin yang boleh hit API (CORS), comma-separated. "
            "'*' = boleh semua (dev). Production set ke domain PWA lo."
        ),
    )

    @field_validator("default_currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper().strip()

    @property
    def allowed_user_id_set(self) -> set[int]:
        """Parse allowed_user_ids into a set of ints; empty set means everyone is allowed."""
        if not self.allowed_user_ids.strip():
            return set()
        out: set[int] = set()
        for raw in self.allowed_user_ids.split(","):
            piece = raw.strip()
            if not piece:
                continue
            try:
                out.add(int(piece))
            except ValueError:
                continue
        return out

    @property
    def cors_allow_origins_list(self) -> list[str]:
        """Parse cors_allow_origins into a list."""
        raw = self.cors_allow_origins.strip()
        if not raw or raw == "*":
            return ["*"]
        return [piece.strip() for piece in raw.split(",") if piece.strip()]


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return memoized application settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
