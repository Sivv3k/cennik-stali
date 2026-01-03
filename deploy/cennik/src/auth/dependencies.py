"""Dependencies FastAPI do ochrony endpointow."""

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import get_settings
from ..models import User
from .session import SessionManager


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Dependency - zwraca zalogowanego usera lub rzuca 401.

    Uzyj dla endpointow API (JSON response).
    """
    settings = get_settings()
    session = SessionManager(settings.secret_key)
    user_id = session.get_user_id(request)

    if not user_id:
        raise HTTPException(status_code=401, detail="Nie zalogowany")

    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Nieprawidlowa sesja")

    return user


async def require_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Dependency - dla stron HTML redirect do /login zamiast 401.

    Uzyj dla endpointow HTML (strony admina).
    """
    settings = get_settings()
    session = SessionManager(settings.secret_key)
    user_id = session.get_user_id(request)

    if not user_id:
        raise HTTPException(
            status_code=303,
            detail="Redirect",
            headers={"Location": "/login"},
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=303,
            detail="Redirect",
            headers={"Location": "/login"},
        )

    return user
