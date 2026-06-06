from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    must_change_password: bool


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    must_change_password: bool

    model_config = {"from_attributes": True}
