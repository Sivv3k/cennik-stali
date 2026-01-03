"""Middleware uprawnień oparty na rolach."""

import hashlib
import secrets
from datetime import datetime
from functools import wraps
from typing import List, Optional, Callable

from fastapi import Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import get_settings
from ..models import User, UserRole, ApiKey
from .session import SessionManager


# ============== ROLE-BASED ACCESS ==============

def require_role(allowed_roles: List[UserRole]):
    """Dependency factory - wymaga jednej z podanych ról.

    Usage:
        @router.get("/admin/users")
        async def list_users(user: User = Depends(require_role([UserRole.ADMIN]))):
            ...
    """
    async def dependency(
        request: Request,
        db: Session = Depends(get_db),
    ) -> User:
        settings = get_settings()
        session = SessionManager(settings.secret_key)
        user_id = session.get_user_id(request)

        if not user_id:
            raise HTTPException(status_code=401, detail="Nie zalogowany")

        user = db.query(User).filter(User.id == user_id).first()

        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Nieprawidłowa sesja")

        if user.is_locked:
            raise HTTPException(status_code=403, detail="Konto zablokowane")

        # Sprawdź rolę
        user_role = UserRole(user.role)
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Brak uprawnień. Wymagana rola: {', '.join(r.value for r in allowed_roles)}"
            )

        return user

    return dependency


# Wygodne aliasy
require_admin = require_role([UserRole.ADMIN])
require_editor = require_role([UserRole.ADMIN, UserRole.EDITOR])
require_viewer = require_role([UserRole.ADMIN, UserRole.EDITOR, UserRole.VIEWER])


# ============== API KEY AUTH ==============

def hash_api_key(key: str) -> str:
    """Hash klucza API (SHA256)."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generuje nowy klucz API."""
    return f"cs_{secrets.token_urlsafe(32)}"


async def get_api_key_user(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Optional[User]:
    """Pobiera użytkownika na podstawie klucza API.

    Zwraca None jeśli brak klucza lub nieprawidłowy.
    """
    if not x_api_key:
        return None

    key_hash = hash_api_key(x_api_key)

    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True,
    ).first()

    if not api_key or not api_key.is_valid:
        return None

    # Aktualizuj last_used
    api_key.last_used = datetime.utcnow()
    db.commit()

    # Pobierz użytkownika
    user = db.query(User).filter(User.id == api_key.user_id).first()

    if not user or not user.is_active:
        return None

    # Dodaj info o uprawnieniach klucza do użytkownika
    user._api_key_permissions = api_key.permissions

    return user


def require_api_permission(permission: str):
    """Dependency - wymaga konkretnego uprawnienia API.

    Permissions:
        - "read" - tylko odczyt
        - "write" - odczyt i zapis
        - "full" - pełny dostęp

    Usage:
        @router.post("/api/prices")
        async def update_prices(user: User = Depends(require_api_permission("write"))):
            ...
    """
    async def dependency(
        request: Request,
        db: Session = Depends(get_db),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ) -> User:
        user = await get_api_key_user(request, db, x_api_key)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Nieprawidłowy lub brakujący klucz API"
            )

        # Sprawdź uprawnienia klucza
        key_permissions = getattr(user, "_api_key_permissions", "read")

        # Hierarchia uprawnień: full > write > read
        permission_levels = {"read": 1, "write": 2, "full": 3}
        required_level = permission_levels.get(permission, 1)
        key_level = permission_levels.get(key_permissions, 1)

        if key_level < required_level:
            raise HTTPException(
                status_code=403,
                detail=f"Klucz API nie ma wymaganych uprawnień: {permission}"
            )

        return user

    return dependency


# ============== COMBINED AUTH (SESSION OR API KEY) ==============

async def get_current_user_or_api(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> User:
    """Autoryzacja przez sesję LUB klucz API.

    Próbuje najpierw klucz API, potem sesję.
    """
    # Spróbuj klucz API
    if x_api_key:
        user = await get_api_key_user(request, db, x_api_key)
        if user:
            return user
        raise HTTPException(status_code=401, detail="Nieprawidłowy klucz API")

    # Spróbuj sesję
    settings = get_settings()
    session = SessionManager(settings.secret_key)
    user_id = session.get_user_id(request)

    if not user_id:
        raise HTTPException(status_code=401, detail="Nie zalogowany")

    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Nieprawidłowa sesja")

    return user
