from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str
    age: int | None = None
    gender: str = ""
    skin_type: str = ""
    lifestyle: dict = Field(default_factory=dict)
    menstrual_health: dict = Field(default_factory=dict)


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    age: int | None = None
    gender: str = ""
    skin_type: str = ""
    lifestyle: dict = Field(default_factory=dict)
    menstrual_health: dict = Field(default_factory=dict)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
