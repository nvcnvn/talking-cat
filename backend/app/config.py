"""Runtime configuration. Every provider is selected here, never hard-wired."""
from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM (OpenAI-compatible chat completions; GLM 5.2) ---
    llm_provider: Literal["openai_compat", "fake"] = "openai_compat"
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_api_key: str = ""
    llm_model: str = "glm-5.2"
    llm_timeout_s: float = 60.0
    llm_temperature: float = 0.7
    llm_max_tokens: int = 220

    # --- Speech to text ---
    stt_provider: Literal["whisper", "mlx_whisper", "fake"] = "whisper"  # whisper = faster-whisper (CPU/CUDA); mlx_whisper = Apple Silicon
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str = "vi"
    whisper_initial_prompt: str = "Xin chào Miu. Miu ơi, mèo Miu ơi."  # vocabulary hint for the cat's name
    mlx_whisper_model: str = "mlx-community/whisper-small-mlx"  # or mlx-community/whisper-large-v3-turbo

    # --- Text to speech ---
    tts_provider: Literal["edge", "piper", "fake"] = "edge"
    tts_fallback: Literal["piper", "fake", "none"] = "piper"  # used when the primary errors or misses the deadline
    tts_deadline_s: float = 2.5
    tts_voice: str = "vi-VN-HoaiMyNeural"
    tts_rate: str = "-5%"
    piper_voice: str = "vi_VN-vais1000-medium"
    piper_data_dir: str = "/opt/piper"

    # --- Safety ---
    safety_llm_check: bool = True  # LLM classifier on the child's input (runs concurrently with generation)
    safety_llm_check_output: bool = False  # LLM classifier on the cat's reply too (adds one LLM round-trip)
    max_user_chars: int = 400
    max_reply_chars: int = 500

    # --- Sessions ---
    session_ttl_s: int = 60 * 30
    session_max_turns: int = 12

    # --- HTTP ---
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"])
    max_upload_bytes: int = 10 * 1024 * 1024


def load_settings() -> Settings:
    return Settings()
