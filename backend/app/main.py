from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.customers import router as customers_router
from app.api.deals import router as deals_router
from app.api.interactions import router as interactions_router
from app.api.inventory import router as inventory_router
from app.api.outreach import router as outreach_router
from app.api.settings import router as settings_router
from app.api.style import router as style_router

app = FastAPI(title="Dealer CRM", version="0.1.0")

app.include_router(auth_router, prefix="/api/auth")
app.include_router(customers_router, prefix="/api/customers")
app.include_router(deals_router, prefix="/api/deals")
app.include_router(interactions_router, prefix="/api/interactions")
app.include_router(inventory_router, prefix="/api/inventory")
app.include_router(chat_router, prefix="/api/chat")
app.include_router(style_router, prefix="/api/style")
app.include_router(outreach_router, prefix="/api/outreach")
app.include_router(settings_router, prefix="/api/settings")

_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
