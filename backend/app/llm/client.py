from typing import Any

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.dependencies import get_current_user
from app.db import AsyncSessionLocal, get_db
from app.models.user import User
from app.services.llm_config import LLMRuntimeConfig, resolve_llm_config
from app.services.llm_log import record_llm_request


class LLMClient:
    def __init__(
        self,
        config: LLMRuntimeConfig,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ):
        self._config = config
        self._session_factory = session_factory or AsyncSessionLocal

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        cfg = self._config
        url = f"{cfg.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {"model": cfg.model, "messages": messages}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {cfg.api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        await record_llm_request(
            self._session_factory,
            url=url,
            model=cfg.model,
            request_payload=payload,
            response_payload=data,
        )
        return data


async def get_llm_client(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LLMClient:
    """FastAPI dependency: an LLMClient configured for the requesting user."""
    config = await resolve_llm_config(db, current_user.id)
    return LLMClient(config)
