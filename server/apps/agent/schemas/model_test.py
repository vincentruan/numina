"""Schemas for POST /test/model endpoint."""

from typing import Literal

from pydantic import BaseModel


class ModelTestRequest(BaseModel):
    provider: Literal["anthropic", "openai", "openai_compatible"]
    api_key: str                        # plaintext, decrypted by backend before sending
    model_id: str
    base_url: str | None = None
    vision_model_id: str | None = None
    test_types: list[Literal["connection", "thinking", "vision", "vision_ocr"]]  # "connection" always runs as prerequisite


class ModelTestResult(BaseModel):
    connected: bool
    message: str
    latency_ms: int | None = None
    thinking_success: bool | None = None
    thinking_message: str | None = None
    thinking_latency_ms: int | None = None
    vision_success: bool | None = None
    vision_message: str | None = None
    vision_latency_ms: int | None = None
    vision_text_success: bool | None = None
    vision_text_message: str | None = None
    vision_text_latency_ms: int | None = None
