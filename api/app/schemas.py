from pydantic import BaseModel, ConfigDict, EmailStr


class APIModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class LoginRequest(APIModel):
    username: str
    password: str


class RegisterRequest(APIModel):
    username: str
    email: EmailStr
    password: str
    role: str


class UserUpdate(APIModel):
    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None


class AuthUser(APIModel):
    id: int
    username: str
    email: str
    role: str


class RegisteredUser(AuthUser):
    is_active: bool


class UserListItem(RegisteredUser):
    created_at: str | None = None
    last_login: str | None = None


class LoginResponse(APIModel):
    message: str
    access_token: str
    refresh_token: str
    user: AuthUser


class RegisterResponse(APIModel):
    message: str
    user: RegisteredUser


class RefreshResponse(APIModel):
    access_token: str
    user: AuthUser


class VerifyResponse(APIModel):
    authenticated: bool
    user: AuthUser


class UserMutationResponse(APIModel):
    message: str
    user: RegisteredUser


class MessageResponse(APIModel):
    message: str


class MyPermissions(APIModel):
    role: str | None = None
    permissions: list[str]
