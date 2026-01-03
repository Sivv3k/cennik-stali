"""Routery API."""

from .materials import router as materials_router
from .prices import router as prices_router
from .import_export import router as import_export_router
from .admin import router as admin_router
from .auth import router as auth_router

__all__ = ["materials_router", "prices_router", "import_export_router", "admin_router", "auth_router"]
