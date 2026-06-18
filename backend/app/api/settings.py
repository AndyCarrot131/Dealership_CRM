from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_manager
from app.auth.hashing import hash_password, verify_password
from app.db import get_db
from app.models.llm_log import LLMRequestLog
from app.models.llm_profile import LLMProfile
from app.models.user import User
from app.schemas.settings import (
    ChangePasswordRequest,
    CreateUserRequest,
    LLMConfigOut,
    LLMConfigUpdate,
    LLMLogItem,
    LLMProfileCreate,
    LLMProfileOut,
    LLMProfileUpdate,
    LLMTestRequest,
    LLMTestResult,
    UserListItem,
)
from app.services.llm_config import (
    activate_profile,
    resolve_llm_config,
    save_llm_config,
    test_llm_connection,
)

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


def _profile_out(p: LLMProfile) -> LLMProfileOut:
    return LLMProfileOut(
        id=p.id,
        name=p.name,
        base_url=p.base_url,
        api_key_masked=_mask_api_key(p.api_key),
        model=p.model,
        is_active=p.is_active,
        is_local=p.is_local,
        created_at=p.created_at,
    )


# ── Legacy single-config endpoints (operate on the active profile) ────────────

@router.get("/llm", response_model=LLMConfigOut)
async def get_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LLMConfigOut:
    cfg = await resolve_llm_config(db, current_user.id)
    return LLMConfigOut(
        base_url=cfg.base_url,
        api_key_masked=_mask_api_key(cfg.api_key),
        model=cfg.model,
    )


@router.put("/llm")
async def update_llm_config(
    body: LLMConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    current = await resolve_llm_config(db, current_user.id)
    final_api_key = body.api_key.strip() if body.api_key.strip() else current.api_key

    await save_llm_config(
        db,
        current_user.id,
        base_url=body.base_url,
        api_key=final_api_key,
        model=body.model,
    )
    await db.commit()
    return {"message": "LLM settings updated"}


# ── Profile CRUD ──────────────────────────────────────────────────────────────

@router.get("/llm/profiles", response_model=list[LLMProfileOut])
async def list_llm_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LLMProfileOut]:
    result = await db.execute(
        select(LLMProfile)
        .where(LLMProfile.user_id == current_user.id)
        .order_by(LLMProfile.created_at)
    )
    return [_profile_out(p) for p in result.scalars()]


@router.post("/llm/profiles", response_model=LLMProfileOut, status_code=201)
async def create_llm_profile(
    body: LLMProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LLMProfileOut:
    existing = await db.execute(
        select(LLMProfile).where(LLMProfile.user_id == current_user.id)
    )
    has_existing = existing.first() is not None

    profile = LLMProfile(
        user_id=current_user.id,
        name=body.name,
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
        is_active=not has_existing,
        is_local=body.is_local,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return _profile_out(profile)


@router.put("/llm/profiles/{profile_id}", response_model=LLMProfileOut)
async def update_llm_profile(
    profile_id: int,
    body: LLMProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LLMProfileOut:
    result = await db.execute(
        select(LLMProfile).where(
            LLMProfile.id == profile_id,
            LLMProfile.user_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.name = body.name
    profile.base_url = body.base_url
    profile.model = body.model
    profile.is_local = body.is_local
    if body.api_key.strip():
        profile.api_key = body.api_key.strip()
    await db.commit()
    await db.refresh(profile)
    return _profile_out(profile)


@router.delete("/llm/profiles/{profile_id}", status_code=204)
async def delete_llm_profile(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(LLMProfile).where(
            LLMProfile.id == profile_id,
            LLMProfile.user_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    all_result = await db.execute(
        select(LLMProfile).where(LLMProfile.user_id == current_user.id)
    )
    all_profiles = list(all_result.scalars())
    if len(all_profiles) == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only LLM profile")

    was_active = profile.is_active
    await db.delete(profile)

    if was_active:
        # Auto-activate the next remaining profile
        remaining = [p for p in all_profiles if p.id != profile_id]
        if remaining:
            remaining[0].is_active = True

    await db.commit()


@router.post("/llm/profiles/{profile_id}/activate")
async def activate_llm_profile(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(LLMProfile).where(
            LLMProfile.id == profile_id,
            LLMProfile.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    await activate_profile(db, current_user.id, profile_id)
    await db.commit()
    return {"message": "Profile activated"}


# ── Test connection ───────────────────────────────────────────────────────────

@router.post("/llm/test", response_model=LLMTestResult)
async def test_llm_inline(
    body: LLMTestRequest,
    _: User = Depends(get_current_user),
) -> LLMTestResult:
    result = await test_llm_connection(body.base_url, body.api_key, body.model)
    return LLMTestResult(ok=result.ok, message=result.message, response_ms=result.response_ms)


@router.post("/llm/profiles/{profile_id}/test", response_model=LLMTestResult)
async def test_llm_profile(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LLMTestResult:
    result = await db.execute(
        select(LLMProfile).where(
            LLMProfile.id == profile_id,
            LLMProfile.user_id == current_user.id,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    test = await test_llm_connection(profile.base_url, profile.api_key, profile.model)
    return LLMTestResult(ok=test.ok, message=test.message, response_ms=test.response_ms)


# ── LLM request log ───────────────────────────────────────────────────────────

@router.get("/llm/logs", response_model=list[LLMLogItem])
async def list_llm_logs(
    _: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, le=500),
) -> list[LLMLogItem]:
    result = await db.execute(
        select(LLMRequestLog).order_by(LLMRequestLog.created_at.desc()).limit(limit)
    )
    items: list[LLMLogItem] = []
    for log in result.scalars():
        # Last user message from the request messages array
        input_text: str | None = None
        if isinstance(log.input, dict):
            messages = log.input.get("messages", [])
            user_msgs = [m.get("content", "") for m in messages if m.get("role") == "user"]
            if user_msgs:
                raw = user_msgs[-1]
                input_text = raw if isinstance(raw, str) else str(raw)

        # Assistant reply from the first choice
        output_text: str | None = None
        if isinstance(log.output, dict):
            choices = log.output.get("choices", [])
            if choices:
                output_text = choices[0].get("message", {}).get("content")

        items.append(
            LLMLogItem(
                id=log.id,
                model=log.model,
                url=log.url,
                created_at=log.created_at,
                input_text=input_text,
                output_text=output_text,
            )
        )
    return items
