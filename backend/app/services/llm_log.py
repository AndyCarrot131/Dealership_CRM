"""Persistence for successful LLM API round-trips (training-data collection)."""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.llm_log import LLMRequestLog

logger = logging.getLogger(__name__)


async def record_llm_request(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    url: str,
    model: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
) -> None:
    """Store one successful request/response pair in llm_request_logs.

    Uses its own session: the request-scoped session is rolled back by the
    assistant's SQL tool, so log rows must not share it. Best-effort — any
    failure is logged and swallowed so a logging problem never breaks chat.
    """
    try:
        async with session_factory() as session:
            session.add(
                LLMRequestLog(
                    url=url,
                    model=model,
                    input=request_payload,
                    output=response_payload,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to record LLM request log (url=%s, model=%s)", url, model)
