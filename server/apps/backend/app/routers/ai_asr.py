"""ASR (speech-to-text) provider configuration & transcription endpoints."""

import logging
import os
import tempfile
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, UploadFile
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors.codes import ErrorCode
from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.models.asr_provider_config import ASRProviderConfig
from apps.backend.app.models.user import User
from apps.backend.app.schemas.asr_config import (
    ASRConfigCreate,
    ASRConfigListResponse,
    ASRConfigResponse,
    ASRConfigUpdate,
    ASRDiffOp,
    ASRLangTestResult,
    ASRStatusResponse,
    ASRTestResult,
    ASRTranscribeResponse,
)
from apps.backend.app.services.ai_crypto import (
    decrypt_api_key,
    encrypt_api_key,
    mask_api_key,
)
from apps.backend.app.services.asr_wer import REFERENCE_TEXTS, compute_wer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asr", tags=["asr"])

# Allowed audio file extensions for transcription
_ALLOWED_AUDIO_EXTENSIONS = {"webm", "wav", "mp3", "ogg", "m4a", "mp4"}
_MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB

# Circuit breaker: auto-disable after this many consecutive failures
_CIRCUIT_FAILURE_THRESHOLD = 3

# Test audio files and their reference languages
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
_TEST_AUDIO_FILES = {
    "zh": "test_asr_audio_zh.mp3",
    "en": "test_asr_audio_en.mp3",
}

# WER threshold: above this percentage, test is considered failed
_WER_FAIL_THRESHOLD = 50.0


def _cfg_to_response(cfg: ASRProviderConfig) -> ASRConfigResponse:
    """Convert DB model to response schema."""
    api_key_masked = None
    if cfg.api_key_encrypted:
        decrypted = decrypt_api_key(cfg.api_key_encrypted)
        if decrypted:
            api_key_masked = mask_api_key(decrypted)

    return ASRConfigResponse(
        id=cfg.id,
        name=cfg.name,
        provider=cfg.provider,
        ai_api_key_masked=api_key_masked,
        base_url=cfg.base_url,
        model_id=cfg.model_id,
        model_2_id=cfg.model_2_id,
        model_3_id=cfg.model_3_id,
        is_active=cfg.is_active,
        display_order=cfg.display_order or 0,
        circuit_state=cfg.circuit_state,
        failure_count=cfg.failure_count,
        last_failure_at=cfg.last_failure_at,
        test_passed=cfg.test_passed,
        test_message=cfg.test_message,
        test_latency_ms=cfg.test_latency_ms,
        tested_at=cfg.tested_at,
    )


async def _get_first_usable_config(
    family_id: int, db: AsyncSession
) -> ASRProviderConfig | None:
    """Find the first active, enabled, circuit-closed ASR config for a family."""
    result = await db.execute(
        select(ASRProviderConfig)
        .where(
            ASRProviderConfig.family_id == family_id,
            ASRProviderConfig.is_active == True,  # noqa: E712
            ASRProviderConfig.circuit_state != "open",
        )
        .order_by(ASRProviderConfig.display_order.asc().nulls_last())
    )
    return result.scalar_one_or_none()


async def _record_failure(cfg: ASRProviderConfig, db: AsyncSession) -> None:
    """Record a transcription failure; auto-disable after threshold."""
    cfg.failure_count += 1
    cfg.last_failure_at = datetime.now(UTC)
    if cfg.failure_count >= _CIRCUIT_FAILURE_THRESHOLD:
        cfg.circuit_state = "open"
        cfg.is_active = False
    await db.commit()


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.get("/config", response_model=ASRConfigListResponse)
async def list_asr_configs(
    current_user: User = Depends(require_adult),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ASRProviderConfig)
        .where(ASRProviderConfig.family_id == current_user.family_id)
        .order_by(ASRProviderConfig.display_order.asc().nulls_last())
    )
    configs = [_cfg_to_response(c) for c in result.scalars().all()]
    return ASRConfigListResponse(configs=configs)


@router.post("/config", response_model=ASRConfigResponse, status_code=201)
async def create_asr_config(
    payload: ASRConfigCreate,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    api_key_encrypted = None
    if payload.ai_api_key:
        api_key_encrypted = encrypt_api_key(payload.ai_api_key)

    cfg = ASRProviderConfig(
        family_id=current_user.family_id,
        name=payload.name,
        provider=payload.provider,
        api_key_encrypted=api_key_encrypted,
        base_url=payload.base_url,
        model_id=payload.model_id,
        model_2_id=payload.model_2_id,
        model_3_id=payload.model_3_id,
        display_order=payload.display_order,
        is_active=False,  # must pass test first
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return _cfg_to_response(cfg)


@router.put("/config/{config_id}", response_model=ASRConfigResponse)
async def update_asr_config(
    config_id: str,
    payload: ASRConfigUpdate,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ASRProviderConfig).where(
            ASRProviderConfig.id == int(config_id),
            ASRProviderConfig.family_id == current_user.family_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise AppError(ErrorCode.NOT_FOUND, details="ASR 配置不存在")

    # Handle is_active toggle: requires test_passed
    if payload.is_active is not None and payload.is_active and not cfg.test_passed:
        raise AppError(ErrorCode.VALIDATION_ERROR, details="请先通过测试后再启用")

    if payload.name is not None:
        cfg.name = payload.name
    if payload.provider is not None:
        cfg.provider = payload.provider
    if payload.base_url is not None:
        cfg.base_url = payload.base_url
    if payload.model_id is not None:
        cfg.model_id = payload.model_id
    if payload.model_2_id is not None:
        cfg.model_2_id = payload.model_2_id
    if payload.model_3_id is not None:
        cfg.model_3_id = payload.model_3_id
    if payload.display_order is not None:
        cfg.display_order = payload.display_order

    # If API key changed, reset test results
    if payload.ai_api_key is not None:
        if payload.ai_api_key == "":
            cfg.api_key_encrypted = None
        else:
            cfg.api_key_encrypted = encrypt_api_key(payload.ai_api_key)
        # Key changed → invalidate test
        cfg.test_passed = None
        cfg.test_message = None
        cfg.test_latency_ms = None
        cfg.tested_at = None
        cfg.is_active = False

    # If is_active is being set explicitly
    if payload.is_active is not None:
        cfg.is_active = payload.is_active

    await db.commit()
    await db.refresh(cfg)
    return _cfg_to_response(cfg)


@router.delete("/config/{config_id}")
async def delete_asr_config(
    config_id: str,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ASRProviderConfig).where(
            ASRProviderConfig.id == int(config_id),
            ASRProviderConfig.family_id == current_user.family_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise AppError(ErrorCode.NOT_FOUND, details="ASR 配置不存在")

    await db.delete(cfg)
    await db.commit()
    return {"ok": True}


# ── Test ──────────────────────────────────────────────────────────────────────


async def _transcribe_file(
    client: AsyncOpenAI,
    model_id: str,
    file_path: str,
    language: str | None = None,
) -> tuple[str, int]:
    """Transcribe a single audio file. Returns (text, latency_ms)."""
    import time
    start = time.monotonic()
    kwargs: dict = {"model": model_id}
    if language:
        kwargs["language"] = language
    with open(file_path, "rb") as f:
        kwargs["file"] = f
        transcription = await client.audio.transcriptions.create(**kwargs)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    text = transcription.text.strip() if transcription.text else ""
    return text, elapsed_ms


@router.post("/config/{config_id}/test", response_model=ASRTestResult)
async def test_asr_config(
    config_id: str,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    """Test ASR config with bilingual audio files and WER comparison."""
    result = await db.execute(
        select(ASRProviderConfig).where(
            ASRProviderConfig.id == int(config_id),
            ASRProviderConfig.family_id == current_user.family_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise AppError(ErrorCode.NOT_FOUND, details="ASR 配置不存在")

    if not cfg.api_key_encrypted:
        cfg.test_passed = False
        cfg.test_message = "未配置 API Key"
        cfg.tested_at = datetime.now(UTC)
        await db.commit()
        return ASRTestResult(success=False, message="未配置 API Key")

    if not cfg.model_id:
        cfg.test_passed = False
        cfg.test_message = "未配置模型 ID"
        cfg.tested_at = datetime.now(UTC)
        await db.commit()
        return ASRTestResult(success=False, message="未配置模型 ID")

    api_key = decrypt_api_key(cfg.api_key_encrypted)
    if not api_key:
        cfg.test_passed = False
        cfg.test_message = "API Key 解密失败"
        cfg.tested_at = datetime.now(UTC)
        await db.commit()
        return ASRTestResult(success=False, message="API Key 解密失败")

    # Check which test audio files exist
    available_tests: dict[str, str] = {}
    for lang, filename in _TEST_AUDIO_FILES.items():
        path = os.path.normpath(os.path.join(_ASSETS_DIR, filename))
        if os.path.isfile(path):
            available_tests[lang] = path

    if not available_tests:
        cfg.test_passed = False
        cfg.test_message = "测试音频文件不存在，请联系管理员"
        cfg.tested_at = datetime.now(UTC)
        await db.commit()
        return ASRTestResult(success=False, message="测试音频文件不存在，请联系管理员")

    client = AsyncOpenAI(api_key=api_key, base_url=cfg.base_url)
    lang_results: list[ASRLangTestResult] = []

    for lang, audio_path in available_tests.items():
        reference = REFERENCE_TEXTS[lang]
        try:
            text, latency_ms = await _transcribe_file(
                client, cfg.model_id, audio_path, language=lang,
            )
            wer = compute_wer(reference, text)
            passed = wer["error_rate_pct"] <= _WER_FAIL_THRESHOLD
            ops = [
                ASRDiffOp(
                    op=op,
                    ref=wer["reference_tokens"][i] if i is not None else None,
                    hyp=wer["hypothesis_tokens"][j] if j is not None else None,
                )
                for op, i, j in wer["ops"]
            ]
            lang_results.append(ASRLangTestResult(
                language=lang,
                reference=reference,
                transcribed=text,
                error_rate_pct=wer["error_rate_pct"],
                error_count=wer["error_count"],
                reference_length=wer["reference_length"],
                passed=passed,
                ops=ops,
                latency_ms=latency_ms,
            ))
        except Exception as e:
            logger.warning("ASR test failed for lang=%s config=%s: %s", lang, cfg.id, e)
            lang_results.append(ASRLangTestResult(
                language=lang,
                reference=reference,
                transcribed="",
                error_rate_pct=100.0,
                error_count=0,
                reference_length=len(reference),
                passed=False,
                ops=[],
                error=str(e)[:200],
            ))

    # Determine overall pass: all languages must pass
    all_passed = all(lr.passed for lr in lang_results)
    summary_parts = []
    for lr in lang_results:
        if lr.error:
            summary_parts.append(f"{lr.language}: 测试失败")
        else:
            status = "通过" if lr.passed else "未通过"
            summary_parts.append(f"{lr.language}: 字错率 {lr.error_rate_pct}% ({status})")

    message = "；".join(summary_parts)

    cfg.test_passed = all_passed
    cfg.test_message = message
    cfg.test_latency_ms = sum(lr.latency_ms or 0 for lr in lang_results)
    cfg.tested_at = datetime.now(UTC)
    if all_passed:
        cfg.circuit_state = "closed"
        cfg.failure_count = 0
    await db.commit()

    return ASRTestResult(
        success=all_passed,
        message=message,
        language_results=lang_results,
    )


# ── Status ────────────────────────────────────────────────────────────────────


@router.get("/status", response_model=ASRStatusResponse)
async def get_asr_status(
    current_user: User = Depends(require_adult),
    db: AsyncSession = Depends(get_db),
):
    """Check if ASR is available for the current family."""
    cfg = await _get_first_usable_config(current_user.family_id, db)
    if cfg:
        return ASRStatusResponse(available=True)
    return ASRStatusResponse(available=False, reason="未配置或未启用 ASR 模型")


# ── Transcribe ────────────────────────────────────────────────────────────────


@router.post("/transcribe", response_model=ASRTranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(require_adult),
    db: AsyncSession = Depends(get_db),
):
    """Transcribe audio using the family's active ASR config."""
    # Validate file extension
    filename = audio.filename or "audio.webm"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=f"不支持的音频格式: {ext}",
        )

    content = await audio.read()
    if len(content) > _MAX_AUDIO_SIZE:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details="文件大小超过限制（最大 10MB）",
        )

    cfg = await _get_first_usable_config(current_user.family_id, db)
    if not cfg:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details="未配置或未启用 ASR 模型，请在设置中配置",
        )

    api_key = decrypt_api_key(cfg.api_key_encrypted or "")
    if not api_key:
        await _record_failure(cfg, db)
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details="API Key 解密失败",
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        client = AsyncOpenAI(api_key=api_key, base_url=cfg.base_url)
        with open(tmp_path, "rb") as f:
            transcription = await client.audio.transcriptions.create(
                model=cfg.model_id,
                file=f,
            )

        text = transcription.text.strip() if transcription.text else ""

        # Success → reset failure counter
        cfg.failure_count = 0
        cfg.circuit_state = "closed"
        await db.commit()

        return ASRTranscribeResponse(text=text)
    except Exception as e:
        logger.warning("ASR transcribe failed for family %s: %s", current_user.family_id, e)
        await _record_failure(cfg, db)
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=f"语音识别失败: {str(e)[:200]}",
        ) from None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
