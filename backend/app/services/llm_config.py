from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_setting import UserSetting

LLM_SETTING_KEYS = ("llm_base_url", "llm_api_key", "llm_model")


@dataclass(frozen=True)
class LLMRuntimeConfig:
    base_url: str
    api_key: str
    model: str


def env_default_config() -> LLMRuntimeConfig:
    from app.config import settings

    return LLMRuntimeConfig(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )


async def resolve_llm_config(db: AsyncSession, user_id: int) -> LLMRuntimeConfig:
    """Return the LLM config for one user, falling back to env defaults per key."""
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
