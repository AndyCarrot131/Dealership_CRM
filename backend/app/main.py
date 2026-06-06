from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.customers import router as customers_router
from app.api.inventory import router as inventory_router

app = FastAPI(title="Dealer CRM", version="0.1.0")

app.include_router(auth_router, prefix="/api/auth")
app.include_router(customers_router, prefix="/api/customers")
app.include_router(inventory_router, prefix="/api/inventory")

_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
