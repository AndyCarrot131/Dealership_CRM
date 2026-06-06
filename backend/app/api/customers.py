from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(tags=["customers"])


@router.get("")
async def list_customers(current_user: User = Depends(get_current_user)) -> dict:
    # Phase 3 implementation
    return {"customers": []}
