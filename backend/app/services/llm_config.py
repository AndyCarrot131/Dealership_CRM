import time
from dataclasses import dataclass

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_profile import LLMProfile
from app.llm import GEMINI_API_KEY_REF, GEMINI_BASE_URL, GEMINI_MODEL


@dataclass(frozen=True)
class LLMRuntimeConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class LLMTestResult:
    ok: bool
    message: str
    response_ms: int | None


def env_default_config() -> LLMRuntimeConfig:
    from app.config import settings

    return LLMRuntimeConfig(
        base_url=GEMINI_BASE_URL,
        api_key=settings.gemini_api_key,
        model=GEMINI_MODEL,
    )


def _resolve_profile_api_key(stored_key: str) -> str:
    if stored_key == GEMINI_API_KEY_REF:
        from app.config import settings

        return settings.gemini_api_key
    return stored_key


async def resolve_llm_profile_config(
    db: AsyncSession, user_id: int, profile_id: int
) -> LLMRuntimeConfig:
    """Return one named LLM profile for the user (must belong to them)."""
    result = await db.execute(
        select(LLMProfile).where(
            LLMProfile.id == profile_id,
            LLMProfile.user_id == user_id,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise ValueError("LLM profile not found")
    return LLMRuntimeConfig(
        base_url=profile.base_url,
        api_key=_resolve_profile_api_key(profile.api_key),
        model=profile.model,
    )


async def resolve_llm_config(db: AsyncSession, user_id: int) -> LLMRuntimeConfig:
    """Return the active cloud profile, or the Gemini environment default."""
    result = await db.execute(
        select(LLMProfile).where(
            LLMProfile.user_id == user_id,
            LLMProfile.is_active.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is not None:
        return LLMRuntimeConfig(
            base_url=profile.base_url,
            api_key=_resolve_profile_api_key(profile.api_key),
            model=profile.model,
        )

    return env_default_config()


async def list_gemini_models() -> list[str]:
    """Return current text/multimodal Gemini models from Google's Models API."""
    from app.config import settings

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key},
        )
        response.raise_for_status()

    excluded_capabilities = (
        "computer-use",
        "embedding",
        "-image",
        "-live",
        "-tts",
    )
    models: list[str] = []
    for item in response.json().get("models", []):
        methods = item.get("supportedGenerationMethods") or []
        name = str(item.get("name") or "").removeprefix("models/")
        if (
            name.startswith("gemini-")
            and "generateContent" in methods
            and not any(marker in name for marker in excluded_capabilities)
        ):
            models.append(name)
    return sorted(set(models))


async def activate_profile(db: AsyncSession, user_id: int, profile_id: int) -> None:
    """Set one profile as active and clear all others for this user. Caller owns commit."""
    await db.execute(
        update(LLMProfile)
        .where(LLMProfile.user_id == user_id)
        .values(is_active=False)
    )
    await db.execute(
        update(LLMProfile)
        .where(LLMProfile.user_id == user_id, LLMProfile.id == profile_id)
        .values(is_active=True)
    )


async def test_llm_connection(base_url: str, api_key: str, model: str) -> LLMTestResult:
    """Send a minimal chat request to verify the LLM endpoint. Does not log the request."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        ms = int((time.monotonic() - start) * 1000)
        return LLMTestResult(ok=True, message="Connection successful", response_ms=ms)
    except httpx.HTTPStatusError as e:
        body = e.response.text[:300]
        return LLMTestResult(ok=False, message=f"HTTP {e.response.status_code}: {body}", response_ms=None)
    except Exception as e:
        return LLMTestResult(ok=False, message=str(e)[:300], response_ms=None)
