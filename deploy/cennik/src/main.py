"""Główna aplikacja FastAPI."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .database import init_db
from .routers import materials_router, prices_router, import_export_router, admin_router, auth_router
from .auth import require_admin
from .auth.permissions import require_role
from .models import User, UserRole

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle aplikacji - inicjalizacja i cleanup."""
    # Startup
    init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.app_name,
    description="System cennikowy dla stali nierdzewnej, czarnej i aluminium",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="src/templates")

# Routers
app.include_router(materials_router)
app.include_router(prices_router)
app.include_router(import_export_router)
app.include_router(admin_router)
app.include_router(auth_router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Strona główna."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": settings.app_name,
        },
    )


@app.get("/cennik", response_class=HTMLResponse)
async def calculator(request: Request):
    """Strona kalkulatora cennika."""
    return templates.TemplateResponse(
        "calculator.html",
        {
            "request": request,
            "title": settings.app_name,
        },
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user: User = Depends(require_admin)):
    """Panel administracyjny - matryce cen."""
    return templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "title": f"{settings.app_name} - Admin",
            "user": user,
        },
    )


@app.get("/admin/grinding", response_class=HTMLResponse)
async def admin_grinding(request: Request, user: User = Depends(require_admin)):
    """Panel administracyjny - matryce szlifu."""
    return templates.TemplateResponse(
        "admin/grinding_matrix.html",
        {
            "request": request,
            "title": f"{settings.app_name} - Matryce Szlifu",
            "user": user,
        },
    )


@app.get("/admin/film", response_class=HTMLResponse)
async def admin_film(request: Request, user: User = Depends(require_admin)):
    """Panel administracyjny - matryce folii."""
    return templates.TemplateResponse(
        "admin/film_matrix.html",
        {
            "request": request,
            "title": f"{settings.app_name} - Matryce Folii",
            "user": user,
        },
    )


@app.get("/admin/materials", response_class=HTMLResponse)
async def admin_materials(request: Request, user: User = Depends(require_admin)):
    """Panel administracyjny - materialy i gatunki stali."""
    return templates.TemplateResponse(
        "admin/materials.html",
        {
            "request": request,
            "title": f"{settings.app_name} - Materialy",
            "user": user,
        },
    )


@app.get("/admin/pricing", response_class=HTMLResponse)
async def admin_pricing(request: Request, user: User = Depends(require_admin)):
    """Panel administracyjny - matryce cen bazowych dla gatunkow."""
    return templates.TemplateResponse(
        "admin/pricing.html",
        {
            "request": request,
            "title": f"{settings.app_name} - Ceny Gatunkow",
            "user": user,
        },
    )


@app.get("/admin/export", response_class=HTMLResponse)
async def admin_export(request: Request, user: User = Depends(require_admin)):
    """Panel administracyjny - eksport cennika."""
    return templates.TemplateResponse(
        "admin/export.html",
        {
            "request": request,
            "title": f"{settings.app_name} - Eksport Cennika",
            "user": user,
        },
    )


@app.get("/admin/import", response_class=HTMLResponse)
async def admin_import(request: Request, user: User = Depends(require_admin)):
    """Panel administracyjny - import cennika."""
    return templates.TemplateResponse(
        "admin/import.html",
        {
            "request": request,
            "title": f"{settings.app_name} - Import Cennika",
            "user": user,
        },
    )


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Panel administracyjny - zarzadzanie uzytkownikami (tylko admin)."""
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "title": f"{settings.app_name} - Uzytkownicy",
            "user": user,
        },
    )


@app.get("/health")
async def health_check():
    """Endpoint do sprawdzania stanu aplikacji."""
    return {"status": "ok", "version": "0.1.0"}


def run():
    """Uruchom serwer (dla CLI)."""
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
