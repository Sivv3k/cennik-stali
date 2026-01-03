"""Schematy Pydantic dla walidacji danych."""

from .pricing import (
    MaterialCreate,
    MaterialResponse,
    BasePriceCreate,
    BasePriceResponse,
    PriceTableRow,
)

from .admin import (
    GrindingPriceCell,
    GrindingMatrixResponse,
    GrindingPriceUpdate,
    GrindingBulkUpdateRequest,
    GrindingBulkUpdateResponse,
    AvailableProvidersResponse,
    FilmPriceCell,
    FilmMatrixResponse,
    FilmPriceUpdate,
    FilmBulkUpdateRequest,
    COSTAInitRequest,
    COSTAInitResponse,
    MatrixExportRequest,
    MatrixImportResult,
    GrindingAvailabilityCheck,
    GrindingAvailabilityResponse,
)

from .user import (
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
    LoginRequest,
    LoginResponse,
)

__all__ = [
    # Pricing
    "MaterialCreate",
    "MaterialResponse",
    "BasePriceCreate",
    "BasePriceResponse",
    "PriceTableRow",
    # Admin - Grinding
    "GrindingPriceCell",
    "GrindingMatrixResponse",
    "GrindingPriceUpdate",
    "GrindingBulkUpdateRequest",
    "GrindingBulkUpdateResponse",
    "AvailableProvidersResponse",
    # Admin - Film
    "FilmPriceCell",
    "FilmMatrixResponse",
    "FilmPriceUpdate",
    "FilmBulkUpdateRequest",
    # Admin - Init
    "COSTAInitRequest",
    "COSTAInitResponse",
    # Admin - Import/Export
    "MatrixExportRequest",
    "MatrixImportResult",
    # Admin - Validation
    "GrindingAvailabilityCheck",
    "GrindingAvailabilityResponse",
    # User
    "UserCreate",
    "UserUpdate",
    "UserPasswordChange",
    "UserPasswordReset",
    "UserResponse",
    "UserListResponse",
    "ApiKeyCreate",
    "ApiKeyResponse",
    "ApiKeyCreatedResponse",
    "ApiKeyListResponse",
    "LoginRequest",
    "LoginResponse",
]
