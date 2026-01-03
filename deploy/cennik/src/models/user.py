"""Model uzytkownika i kluczy API systemu."""

from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class UserRole(str, Enum):
    """Role uzytkowników w systemie."""
    ADMIN = "admin"      # Pełny dostęp + zarządzanie użytkownikami
    EDITOR = "editor"    # Edycja cen, import/export
    VIEWER = "viewer"    # Tylko podgląd


class User(Base):
    """Model uzytkownika systemu."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Dane logowania
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))

    # Rola i status
    role: Mapped[str] = mapped_column(String(20), default=UserRole.VIEWER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Bezpieczeństwo konta
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Śledzenie
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Relacje
    api_keys: Mapped[List["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        """Czy użytkownik ma rolę admin."""
        return self.role == UserRole.ADMIN.value

    @property
    def is_editor(self) -> bool:
        """Czy użytkownik ma rolę editor lub wyższą."""
        return self.role in (UserRole.ADMIN.value, UserRole.EDITOR.value)

    @property
    def is_locked(self) -> bool:
        """Czy konto jest zablokowane."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


class ApiKey(Base):
    """Klucze API dla integracji zewnętrznych."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Właściciel klucza
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    # Klucz (przechowujemy hash)
    key_hash: Mapped[str] = mapped_column(String(255))  # SHA256 hash klucza
    key_prefix: Mapped[str] = mapped_column(String(8))  # Pierwsze 8 znaków (do identyfikacji)

    # Metadane
    name: Mapped[str] = mapped_column(String(100))      # Nazwa/opis klucza
    permissions: Mapped[str] = mapped_column(String(50), default="read")  # read, write, full

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Śledzenie użycia
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def is_expired(self) -> bool:
        """Czy klucz wygasł."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Czy klucz jest ważny (aktywny i nie wygasł)."""
        return self.is_active and not self.is_expired

    def __repr__(self) -> str:
        return f"<ApiKey {self.key_prefix}... ({self.name})>"
