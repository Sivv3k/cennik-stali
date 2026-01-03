"""Modul autentykacji - sesje i ochrona routerow."""

from .session import SessionManager
from .dependencies import get_current_user, require_admin
from .permissions import (
    require_role,
    require_editor,
    require_viewer,
    require_api_permission,
    get_current_user_or_api,
    get_api_key_user,
    hash_api_key,
    generate_api_key,
)

__all__ = [
    "SessionManager",
    "get_current_user",
    "require_admin",
    # Permissions
    "require_role",
    "require_editor",
    "require_viewer",
    "require_api_permission",
    "get_current_user_or_api",
    "get_api_key_user",
    "hash_api_key",
    "generate_api_key",
]
