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
        timeout: float = 60,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        cfg = self._config
        url = f"{cfg.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {"model": cfg.model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = tools
            if not cfg.is_local:
                payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=timeout) as client:
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
            request_payload=_redact_images(payload),
            response_payload=data,
        )
        return data


def _redact_images(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace base64 image_url parts with a placeholder so multi-MB blobs
    don't get written into llm_request_logs."""
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload

    redacted_messages = []
    changed = False
    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url_val = (part.get("image_url") or {}).get("url", "")
                    parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"<image omitted, {len(url_val)} chars>"},
                        }
                    )
                    changed = True
                else:
                    parts.append(part)
            redacted_messages.append({**msg, "content": parts})
        else:
            redacted_messages.append(msg)

    if not changed:
        return payload
    return {**payload, "messages": redacted_messages}


async def get_llm_client(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LLMClient:
    """FastAPI dependency: an LLMClient configured for the requesting user."""
    config = await resolve_llm_config(db, current_user.id)
    return LLMClient(config)
