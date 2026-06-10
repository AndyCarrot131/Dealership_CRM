from typing import Any

import httpx

from app.services.llm_config import get_llm_runtime_config


class LLMClient:
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        cfg = get_llm_runtime_config()
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


llm_client = LLMClient()
