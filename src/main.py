"""Główna aplikacja FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .database import init_db
from .routers import materials_router, prices_router, import_export_router

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
