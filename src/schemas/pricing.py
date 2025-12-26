"""Schematy dla cennika."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..models.material import MaterialCategory
from ..models.price import SourceType
from ..models.surface import SurfaceType, Finish


# === Material Schemas ===

class MaterialBase(BaseModel):
    """Bazowy schemat materiału."""

    name: str
    category: MaterialCategory
    grade: str
    description: Optional[str] = None
    density: Optional[float] = None


class MaterialCreate(MaterialBase):
    """Schemat do tworzenia materiału."""

    pass


class MaterialResponse(MaterialBase):
    """Schemat odpowiedzi dla materiału."""

    model_config = ConfigDict(from_attributes=True)

    id: int


# === Price Schemas ===

class PriceBase(BaseModel):
    """Bazowy schemat ceny."""

    thickness: float
    width: Optional[float] = None
    length: Optional[float] = None
    source_type: SourceType
    price_per_kg: Optional[float] = None
    price_per_m2: Optional[float] = None
    price_per_piece: Optional[float] = None
    currency: str = "PLN"
    min_order_qty: Optional[float] = None
    min_order_unit: Optional[str] = None
    notes: Optional[str] = None


class PriceCreate(PriceBase):
    """Schemat do tworzenia ceny."""

    material_id: int
    surface_id: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


class PriceResponse(PriceBase):
    """Schemat odpowiedzi dla ceny."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    surface_id: Optional[int] = None
    valid_from: datetime
    valid_to: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# === Table View Schemas ===

class PriceTableRow(BaseModel):
    """Wiersz tabeli cennikowej (widok dla użytkownika)."""

    model_config = ConfigDict(from_attributes=True)

    # Materiał
    material_name: str
    material_category: MaterialCategory
    grade: str

    # Wymiary
    thickness: float
    width: Optional[float] = None
    length: Optional[float] = None

    # Źródło i powierzchnia
    source_type: SourceType
    surface_type: Optional[SurfaceType] = None
    finish: Optional[Finish] = None
    protective_film: bool = False

    # Ceny
    price_per_kg: Optional[float] = None
    price_per_m2: Optional[float] = None
    currency: str = "PLN"
