import time
from dataclasses import dataclass

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_profile import LLMProfile
from app.models.user_setting import UserSetting

LLM_SETTING_KEYS = ("llm_base_url", "llm_api_key", "llm_model")


@dataclass(frozen=True)
class LLMRuntimeConfig:
    base_url: str
    api_key: str
    model: str
    is_local: bool = False


@dataclass(frozen=True)
class LLMTestResult:
    ok: bool
    message: str
    response_ms: int | None


def env_default_config() -> LLMRuntimeConfig:
    from app.config import settings

    return LLMRuntimeConfig(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )


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
        api_key=profile.api_key,
        model=profile.model,
        is_local=profile.is_local,
    )


async def resolve_llm_config(db: AsyncSession, user_id: int) -> LLMRuntimeConfig:
    """Return the LLM config for one user: active profile → old user_settings → env defaults."""
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
            api_key=profile.api_key,
            model=profile.model,
            is_local=profile.is_local,
        )

    # Fall back to legacy user_settings keys
    result = await db.execute(
        select(UserSetting).where(
            UserSetting.user_id == user_id,
            UserSetting.key.in_(LLM_SETTING_KEYS),
        )
    )
    rows = {row.key: row.value for row in result.scalars()}
    defaults = env_default_config()
    return LLMRuntimeConfig(
        base_url=rows.get("llm_base_url", defaults.base_url),
        api_key=rows.get("llm_api_key", defaults.api_key),
        model=rows.get("llm_model", defaults.model),
    )


async def save_llm_config(
    db: AsyncSession,
    user_id: int,
    base_url: str,
    api_key: str,
    model: str,
) -> None:
    """Upsert the three llm_* rows for one user. Caller owns the commit."""
    values = {"llm_base_url": base_url, "llm_api_key": api_key, "llm_model": model}
    result = await db.execute(
        select(UserSetting).where(
            UserSetting.user_id == user_id,
            UserSetting.key.in_(LLM_SETTING_KEYS),
        )
    )
    existing = {row.key: row for row in result.scalars()}
    for key, value in values.items():
        row = existing.get(key)
        if row is not None:
            row.value = value
        else:
            db.add(UserSetting(user_id=user_id, key=key, value=value))


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
