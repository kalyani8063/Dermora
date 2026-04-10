from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str
    age: int | None = None
    gender: str = ""
    birthdate: str | None = None
    skin_type: str = ""
    lifestyle: dict = Field(default_factory=dict)
    menstrual_health: dict = Field(default_factory=dict)

    onboarding_completed: bool = False
    acne_type: list[str] = Field(default_factory=list)
    stress_level: str = ""
    hormonal_issues: str = ""
    diet_type: str = ""
    activity_level: str = ""


class RegisterOtpSendRequest(BaseModel):
    name: str
    email: str


class EmailOtpRequest(BaseModel):
    email: str


class OtpVerifyRequest(BaseModel):
    email: str
    otp: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    age: int | None = None
    gender: str = ""
    birthdate: str | None = None
    skin_type: str = ""
    lifestyle: dict = Field(default_factory=dict)
    menstrual_health: dict = Field(default_factory=dict)


class ProfileUpdateRequest(BaseModel):
    email: str
    name: str
    age: int | None = None
    gender: str = ""
    birthdate: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordResetConfirmRequest(BaseModel):
    email: str
    new_password: str


class OnboardingRequest(BaseModel):
    acne_type: list[str] = Field(default_factory=list)
    stress_level: str = ""
    hormonal_issues: str = ""
    diet_type: str = ""
    activity_level: str = ""
    skipped: bool = False


class OtpRequestResponse(BaseModel):
    message: str
    expires_in_seconds: int
    resend_in_seconds: int
    development_code: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
