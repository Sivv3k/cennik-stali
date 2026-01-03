"""Router autentykacji - logowanie, wylogowanie i zarządzanie użytkownikami."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Response, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import get_settings
from ..models import User, UserRole
from ..services.auth import AuthService
from ..auth.session import SessionManager
from ..auth.dependencies import get_current_user
from ..auth.permissions import require_role
from ..schemas.user import (
    UserCreate,
    UserUpdate,
    UserPasswordChange,
    UserPasswordReset,
    UserResponse,
    UserListResponse,
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
)

router = APIRouter(tags=["auth"])

templates = Jinja2Templates(directory="src/templates")


# ============== LOGIN/LOGOUT ==============

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Strona logowania."""
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "title": "Logowanie",
            "error": None,
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Przetworz formularz logowania."""
    settings = get_settings()
    auth = AuthService(db)
    user = auth.authenticate(username, password)

    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "title": "Logowanie",
                "error": "Nieprawidlowy login lub haslo",
            },
            status_code=401,
        )

    # Zaktualizuj last_login
    user.last_login = datetime.utcnow()
    db.commit()

    # Sprawdź czy wymaga zmiany hasła
    if user.must_change_password:
        response = RedirectResponse("/auth/change-password", status_code=302)
    else:
        response = RedirectResponse("/admin", status_code=302)

    # Utworz sesje
    session = SessionManager(settings.secret_key)
    session.create_session(response, user.id)

    return response


@router.get("/logout")
async def logout():
    """Wyloguj uzytkownika."""
    settings = get_settings()
    response = RedirectResponse("/login", status_code=302)
    session = SessionManager(settings.secret_key)
    session.destroy_session(response)

    return response


# ============== CHANGE PASSWORD (USER) ==============

@router.get("/auth/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Strona zmiany hasła."""
    return templates.TemplateResponse(
        "auth/change_password.html",
        {
            "request": request,
            "title": "Zmień hasło",
            "user": current_user,
            "error": None,
            "success": None,
        },
    )


@router.post("/auth/change-password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Zmień hasło użytkownika."""
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "auth/change_password.html",
            {
                "request": request,
                "title": "Zmień hasło",
                "user": current_user,
                "error": "Hasła nie są zgodne",
                "success": None,
            },
        )

    if len(new_password) < 6:
        return templates.TemplateResponse(
            "auth/change_password.html",
            {
                "request": request,
                "title": "Zmień hasło",
                "user": current_user,
                "error": "Hasło musi mieć minimum 6 znaków",
                "success": None,
            },
        )

    auth = AuthService(db)
    success, message = auth.change_password(current_user.id, current_password, new_password)

    if not success:
        return templates.TemplateResponse(
            "auth/change_password.html",
            {
                "request": request,
                "title": "Zmień hasło",
                "user": current_user,
                "error": message,
                "success": None,
            },
        )

    return templates.TemplateResponse(
        "auth/change_password.html",
        {
            "request": request,
            "title": "Zmień hasło",
            "user": current_user,
            "error": None,
            "success": "Hasło zostało zmienione",
        },
    )


@router.put("/api/auth/change-password")
async def api_change_password(
    data: UserPasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API: Zmień własne hasło."""
    auth = AuthService(db)
    success, message = auth.change_password(
        current_user.id,
        data.current_password,
        data.new_password,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


# ============== ADMIN: USER MANAGEMENT ==============

@router.get("/api/admin/users", response_model=UserListResponse)
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Lista wszystkich użytkowników (tylko admin)."""
    auth = AuthService(db)
    users = auth.list_users()
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=len(users),
    )


@router.post("/api/admin/users", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Utwórz nowego użytkownika (tylko admin)."""
    auth = AuthService(db)

    try:
        user = auth.create_user(
            username=data.username,
            password=data.password,
            email=data.email,
            role=data.role,
            created_by_id=current_user.id,
            must_change_password=True,  # Wymaga zmiany hasła przy pierwszym logowaniu
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return UserResponse.model_validate(user)


@router.get("/api/admin/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Pobierz dane użytkownika (tylko admin)."""
    auth = AuthService(db)
    user = auth.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")

    return UserResponse.model_validate(user)


@router.put("/api/admin/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Aktualizuj użytkownika (tylko admin)."""
    # Nie można edytować samego siebie (zmiana roli)
    if user_id == current_user.id and data.role and data.role != UserRole(current_user.role):
        raise HTTPException(status_code=400, detail="Nie można zmienić własnej roli")

    auth = AuthService(db)
    user = auth.update_user(
        user_id,
        email=data.email,
        role=data.role,
        is_active=data.is_active,
    )

    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")

    return UserResponse.model_validate(user)


@router.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Usuń użytkownika (tylko admin)."""
    # Nie można usunąć samego siebie
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Nie można usunąć własnego konta")

    auth = AuthService(db)
    if not auth.delete_user(user_id):
        raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")

    return {"success": True, "message": "Użytkownik usunięty"}


@router.post("/api/admin/users/{user_id}/reset-password", response_model=UserResponse)
async def reset_user_password(
    user_id: int,
    data: UserPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Resetuj hasło użytkownika (tylko admin)."""
    auth = AuthService(db)
    user = auth.reset_password(user_id, data.new_password, data.must_change)

    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")

    return UserResponse.model_validate(user)


@router.post("/api/admin/users/{user_id}/unlock", response_model=UserResponse)
async def unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Odblokuj konto użytkownika (tylko admin)."""
    auth = AuthService(db)
    user = auth.unlock_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")

    return UserResponse.model_validate(user)


# ============== ADMIN: API KEY MANAGEMENT ==============

@router.get("/api/admin/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    user_id: Optional[int] = Query(None, description="Filtruj po ID użytkownika"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Lista kluczy API (tylko admin)."""
    auth = AuthService(db)
    keys = auth.list_api_keys(user_id)
    return ApiKeyListResponse(
        api_keys=[ApiKeyResponse.model_validate(k) for k in keys],
        total=len(keys),
    )


@router.post("/api/admin/api-keys", response_model=ApiKeyCreatedResponse)
async def create_api_key(
    data: ApiKeyCreate,
    user_id: int = Query(..., description="ID użytkownika dla klucza"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Utwórz nowy klucz API (tylko admin). Klucz wyświetlany tylko raz!"""
    auth = AuthService(db)

    try:
        api_key, raw_key = auth.create_api_key(
            user_id=user_id,
            name=data.name,
            permissions=data.permissions,
            expires_in_days=data.expires_in_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build response with raw_key included
    response_data = {
        "id": api_key.id,
        "user_id": api_key.user_id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "permissions": api_key.permissions,
        "is_active": api_key.is_active,
        "created_at": api_key.created_at,
        "last_used": api_key.last_used,
        "expires_at": api_key.expires_at,
        "api_key": raw_key,
    }

    return ApiKeyCreatedResponse(**response_data)


@router.delete("/api/admin/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Usuń klucz API (tylko admin)."""
    auth = AuthService(db)

    if not auth.delete_api_key(key_id):
        raise HTTPException(status_code=404, detail="Klucz API nie znaleziony")

    return {"success": True, "message": "Klucz API usunięty"}


@router.post("/api/admin/api-keys/{key_id}/deactivate", response_model=ApiKeyResponse)
async def deactivate_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Dezaktywuj klucz API (tylko admin)."""
    auth = AuthService(db)
    api_key = auth.deactivate_api_key(key_id)

    if not api_key:
        raise HTTPException(status_code=404, detail="Klucz API nie znaleziony")

    return ApiKeyResponse.model_validate(api_key)
