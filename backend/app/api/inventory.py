from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(tags=["inventory"])


@router.get("")
async def list_inventory(current_user: User = Depends(get_current_user)) -> dict:
    # Phase 3 implementation
    return {"inventory": []}
