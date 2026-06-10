from typing import Any

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models.user import User
from app.services.llm_config import LLMRuntimeConfig, resolve_llm_config


class LLMClient:
    def __init__(self, config: LLMRuntimeConfig):
        self._config = config

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        cfg = self._config
        payload: dict[str, Any] = {"model": cfg.model, "messages": messages}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{cfg.base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {cfg.api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()


async def get_llm_client(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LLMClient:
    """FastAPI dependency: an LLMClient configured for the requesting user."""
    config = await resolve_llm_config(db, current_user.id)
    return LLMClient(config)
