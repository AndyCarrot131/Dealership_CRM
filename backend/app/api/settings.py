from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_manager
from app.auth.hashing import hash_password, verify_password
from app.db import get_db
from app.models.app_setting import AppSetting
from app.models.user import User
from app.schemas.settings import (
    ChangePasswordRequest,
    CreateUserRequest,
    LLMConfigOut,
    LLMConfigUpdate,
    UserListItem,
)
from app.services.llm_config import get_llm_runtime_config, set_llm_runtime_config

router = APIRouter(tags=["settings"])


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.password_hash = hash_password(body.new_password)
    current_user.must_change_password = False
    await db.commit()
    return {"message": "Password changed"}


@router.get("/users", response_model=list[UserListItem])
async def list_users(
    _: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


@router.post("/users", response_model=UserListItem, status_code=201)
async def create_user(
    body: CreateUserRequest,
    _: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> User:
    if body.role not in ("sales", "manager"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Role must be 'sales' or 'manager'")
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    user = User(
        email=body.email,
        name=body.name,
        role=body.role,
        password_hash=hash_password(body.password),
        must_change_password=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _mask_api_key(key: str) -> str:
    if len(key) <= 4:
        return "****"
    return "***" + key[-4:]


@router.get("/llm", response_model=LLMConfigOut)
async def get_llm_config(
    _: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> LLMConfigOut:
    cfg = get_llm_runtime_config()
    try:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key.in_(["llm_base_url", "llm_api_key", "llm_model"]))
        )
        rows = {row.key: row.value for row in result.scalars()}
    except Exception:
        rows = {}
    return LLMConfigOut(
        base_url=rows.get("llm_base_url", cfg.base_url),
        api_key_masked=_mask_api_key(rows.get("llm_api_key", cfg.api_key)),
        model=rows.get("llm_model", cfg.model),
    )


@router.put("/llm")
async def update_llm_config(
    body: LLMConfigUpdate,
    _: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> dict:
    existing_key_row = await db.execute(select(AppSetting).where(AppSetting.key == "llm_api_key"))
    existing_row = existing_key_row.scalar_one_or_none()

    current_api_key = existing_row.value if existing_row else get_llm_runtime_config().api_key
    final_api_key = body.api_key.strip() if body.api_key.strip() else current_api_key

    updates = {
        "llm_base_url": body.base_url,
        "llm_api_key": final_api_key,
        "llm_model": body.model,
    }

    for key, value in updates.items():
        row_result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        row = row_result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))

    await db.commit()
    set_llm_runtime_config(
        base_url=updates["llm_base_url"],
        api_key=final_api_key,
        model=updates["llm_model"],
    )
    return {"message": "LLM settings updated"}
