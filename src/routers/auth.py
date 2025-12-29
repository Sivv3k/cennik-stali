"""Router autentykacji - logowanie i wylogowanie."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import get_settings
from ..services.auth import AuthService
from ..auth.session import SessionManager

router = APIRouter(tags=["auth"])

templates = Jinja2Templates(directory="src/templates")


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

    # Utworz sesje
    response = RedirectResponse("/admin", status_code=302)
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
