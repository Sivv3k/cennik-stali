"""Schematy Pydantic dla użytkowników i kluczy API."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, field_validator

from ..models.user import UserRole


# ============== USER SCHEMAS ==============

class UserBase(BaseModel):
    """Podstawowe dane użytkownika."""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    """Schemat tworzenia użytkownika."""
    password: str = Field(..., min_length=6, max_length=100)
    role: UserRole = Field(default=UserRole.VIEWER)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Walidacja nazwy użytkownika."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username może zawierać tylko litery, cyfry, _ i -")
        return v.lower()


class UserUpdate(BaseModel):
    """Schemat aktualizacji użytkownika."""
    email: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserPasswordChange(BaseModel):
    """Zmiana hasła przez użytkownika."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=100)


class UserPasswordReset(BaseModel):
    """Reset hasła przez admina."""
    new_password: str = Field(..., min_length=6, max_length=100)
    must_change: bool = Field(default=True, description="Wymaga zmiany hasła przy logowaniu")


class UserResponse(BaseModel):
    """Odpowiedź z danymi użytkownika."""
    id: int
    username: str
    email: Optional[str]
    role: str
    is_active: bool
    must_change_password: bool
    failed_login_attempts: int
    locked_until: Optional[datetime]
    created_at: datetime
    last_login: Optional[datetime]
    created_by_id: Optional[int]

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Lista użytkowników."""
    users: List[UserResponse]
    total: int


# ============== API KEY SCHEMAS ==============

class ApiKeyCreate(BaseModel):
    """Schemat tworzenia klucza API."""
    name: str = Field(..., min_length=1, max_length=100, description="Nazwa/opis klucza")
    permissions: str = Field(default="read", description="Uprawnienia: read, write, full")
    expires_in_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Ważność w dniach (None = bezterminowo)"
    )

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: str) -> str:
        """Walidacja uprawnień."""
        allowed = ["read", "write", "full"]
        if v not in allowed:
            raise ValueError(f"Permissions musi być jednym z: {', '.join(allowed)}")
        return v


class ApiKeyResponse(BaseModel):
    """Odpowiedź z danymi klucza (bez wartości klucza)."""
    id: int
    user_id: int
    name: str
    key_prefix: str
    permissions: str
    is_active: bool
    created_at: datetime
    last_used: Optional[datetime]
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Odpowiedź po utworzeniu klucza (zawiera pełny klucz - tylko raz!)."""
    api_key: str = Field(..., description="Pełny klucz API - wyświetlany tylko raz!")


class ApiKeyListResponse(BaseModel):
    """Lista kluczy API."""
    api_keys: List[ApiKeyResponse]
    total: int


# ============== AUTH SCHEMAS ==============

class LoginRequest(BaseModel):
    """Żądanie logowania."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Odpowiedź po zalogowaniu."""
    success: bool
    message: str
    user: Optional[UserResponse] = None
    must_change_password: bool = False
