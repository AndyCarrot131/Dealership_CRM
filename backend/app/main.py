from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.customers import router as customers_router
from app.api.interactions import router as interactions_router
from app.api.inventory import router as inventory_router
from app.api.outreach import router as outreach_router
from app.api.settings import router as settings_router
from app.api.style import router as style_router
from app.config import settings
from app.db import AsyncSessionLocal
from app.models.app_setting import AppSetting
from app.services.llm_config import set_llm_runtime_config


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AppSetting).where(
                    AppSetting.key.in_(["llm_base_url", "llm_api_key", "llm_model"])
                )
            )
            rows = {row.key: row.value for row in result.scalars()}
            if rows:
                set_llm_runtime_config(
                    base_url=rows.get("llm_base_url", settings.llm_base_url),
                    api_key=rows.get("llm_api_key", settings.llm_api_key),
                    model=rows.get("llm_model", settings.llm_model),
                )
    except Exception:
        pass
    yield


app = FastAPI(title="Dealer CRM", version="0.1.0", lifespan=lifespan)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(customers_router, prefix="/api/customers")
app.include_router(interactions_router, prefix="/api/interactions")
app.include_router(inventory_router, prefix="/api/inventory")
app.include_router(chat_router, prefix="/api/chat")
app.include_router(style_router, prefix="/api/style")
app.include_router(outreach_router, prefix="/api/outreach")
app.include_router(settings_router, prefix="/api/settings")

_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
