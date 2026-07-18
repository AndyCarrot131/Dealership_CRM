from datetime import datetime
from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class CreateUserRequest(BaseModel):
    email: str
    name: str
    role: str
    password: str = Field(min_length=8)


class UserListItem(BaseModel):
    id: int
    email: str
    name: str
    role: str
    must_change_password: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LLMConfigOut(BaseModel):
    base_url: str
    api_key_masked: str
    model: str


class LLMProfileOut(BaseModel):
    id: int
    name: str
    base_url: str
    api_key_masked: str
    model: str
    is_active: bool
    is_system: bool
    created_at: datetime


class LLMProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str
    api_key: str
    model: str


class LLMProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str
    api_key: str  # blank = keep existing
    model: str


class LLMTestRequest(BaseModel):
    base_url: str
    api_key: str
    model: str


class LLMTestResult(BaseModel):
    ok: bool
    message: str
    response_ms: int | None


class LLMLogItem(BaseModel):
    id: int
    model: str
    url: str
    created_at: datetime
    input_text: str | None
    output_text: str | None
