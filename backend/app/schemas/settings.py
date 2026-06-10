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


class LLMConfigUpdate(BaseModel):
    base_url: str
    api_key: str
    model: str
