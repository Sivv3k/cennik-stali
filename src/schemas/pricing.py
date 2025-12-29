"""Schematy dla cennika - rozbudowane dla wszystkich typów stali."""

from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from ..models.material import MaterialCategory, SurfaceFinish
from ..models.processing import GrindingProvider, FilmType


# === Material Group Schemas ===

class MaterialGroupBase(BaseModel):
    """Bazowy schemat grupy materiałów."""

    name: str
    category: MaterialCategory
    description: Optional[str] = None
    display_order: int = 0


class MaterialGroupCreate(MaterialGroupBase):
    """Schemat do tworzenia grupy materiałów."""
    pass


class MaterialGroupUpdate(BaseModel):
    """Schemat do aktualizacji grupy materiałów."""

    name: Optional[str] = None
    category: Optional[MaterialCategory] = None
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class MaterialGroupResponse(MaterialGroupBase):
    """Schemat odpowiedzi dla grupy materiałów."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool = True


class MaterialGroupWithMaterials(MaterialGroupResponse):
    """Grupa materiałów z listą materiałów."""

    materials: list["MaterialResponse"] = []


# === Material Schemas ===

class MaterialBase(BaseModel):
    """Bazowy schemat materiału."""

    name: str
    category: MaterialCategory
    grade: str
    description: Optional[str] = None
    density: float = 7.9
    standard: Optional[str] = None
    equivalent_grades: Optional[str] = None
    composition: Optional[str] = None
    tensile_strength: Optional[str] = None
    yield_strength: Optional[str] = None
    applications: Optional[str] = None
    display_order: int = 0
    group_id: Optional[int] = None


class MaterialCreate(MaterialBase):
    """Schemat do tworzenia materiału."""
    pass


class MaterialUpdate(BaseModel):
    """Schemat do aktualizacji materiału."""

    name: Optional[str] = None
    category: Optional[MaterialCategory] = None
    grade: Optional[str] = None
    description: Optional[str] = None
    density: Optional[float] = None
    standard: Optional[str] = None
    equivalent_grades: Optional[str] = None
    composition: Optional[str] = None
    tensile_strength: Optional[str] = None
    yield_strength: Optional[str] = None
    applications: Optional[str] = None
    display_order: Optional[int] = None
    group_id: Optional[int] = None
    is_active: Optional[bool] = None


class MaterialResponse(MaterialBase):
    """Schemat odpowiedzi dla materiału."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool = True


class MaterialWithGroup(MaterialResponse):
    """Materiał z informacją o grupie."""

    group: Optional[MaterialGroupResponse] = None


# === Base Price Schemas ===

class BasePriceBase(BaseModel):
    """Bazowy schemat ceny."""

    surface_finish: str
    thickness: float
    width: float
    length: float
    price_pln_per_kg: float
    notes: Optional[str] = None


class BasePriceCreate(BasePriceBase):
    """Schemat do tworzenia ceny bazowej."""

    material_id: int
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


class BasePriceResponse(BasePriceBase):
    """Schemat odpowiedzi dla ceny bazowej."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    valid_from: datetime
    valid_to: Optional[datetime] = None
    is_active: bool = True


# === Grinding Schemas ===

class GrindingPriceBase(BaseModel):
    """Bazowy schemat ceny szlifu."""

    provider: GrindingProvider
    grit: Optional[str] = None
    width_variant: Optional[str] = None
    thickness: float
    price_pln_per_kg: float
    with_sb: bool = False


class GrindingPriceCreate(GrindingPriceBase):
    """Schemat do tworzenia ceny szlifu."""
    pass


class GrindingPriceResponse(GrindingPriceBase):
    """Schemat odpowiedzi dla ceny szlifu."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool = True


# === Film Schemas ===

class FilmPriceBase(BaseModel):
    """Bazowy schemat ceny folii."""

    film_type: FilmType
    thickness: float
    price_pln_per_kg: float


class FilmPriceCreate(FilmPriceBase):
    """Schemat do tworzenia ceny folii."""
    pass


class FilmPriceResponse(FilmPriceBase):
    """Schemat odpowiedzi dla ceny folii."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool = True


# === Price Calculation Schemas ===

class PriceCalculationRequest(BaseModel):
    """Request do kalkulacji ceny."""

    material_id: int
    surface_finish: str
    thickness: float
    width: float
    length: float
    film_type: Optional[FilmType] = None
    grinding_provider: Optional[GrindingProvider] = None
    grinding_grit: Optional[str] = None
    grinding_width_variant: Optional[str] = None
    with_sb: bool = False


class PriceBreakdownResponse(BaseModel):
    """Szczegółowe rozbicie ceny."""

    # Ceny składowe (PLN/kg)
    base_price_pln_kg: float
    film_cost_pln_kg: float = 0.0
    grinding_cost_pln_kg: float = 0.0

    # Cena końcowa
    total_price_pln_kg: float
    total_price_eur_kg: float

    # Kurs waluty
    exchange_rate: float

    # Wymiary i waga
    dimensions: dict
    weight_kg: float
    area_m2: float

    # Konfiguracja
    configuration: dict

    # Uwagi
    notes: Optional[str] = None


# === Table View Schemas ===

class PriceTableRow(BaseModel):
    """Wiersz tabeli cennikowej (widok dla użytkownika)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    material_name: str
    grade: str
    category: str

    # Wymiary
    surface_finish: str
    thickness: float
    width: float
    length: float

    # Ceny
    price_pln_per_kg: float
    price_eur_per_kg: float

    # Uwagi
    notes: Optional[str] = None


class PriceTableFilter(BaseModel):
    """Filtry do tabeli cennikowej."""

    category: Optional[MaterialCategory] = None
    grade: Optional[str] = None
    surface_finish: Optional[str] = None
    thickness_min: Optional[float] = None
    thickness_max: Optional[float] = None
    width: Optional[float] = None


# === Processing Options Schemas ===

class ProcessingOptionsResponse(BaseModel):
    """Dostępne opcje obróbki."""

    processing_allowed: bool
    notes: Optional[str] = None
    films: list[dict]
    grindings: list[dict]


# === Import/Export Schemas ===

class ImportResultResponse(BaseModel):
    """Wynik importu danych."""

    success: bool
    sheets_processed: int
    materials_imported: int
    base_prices_imported: int
    grinding_prices_imported: int
    film_prices_imported: int
    modifiers_imported: int
    errors: list[dict]
    warnings: list[str]


class ExchangeRateBase(BaseModel):
    """Bazowy schemat kursu walut."""

    currency_from: str = "EUR"
    currency_to: str = "PLN"
    rate: float


class ExchangeRateCreate(ExchangeRateBase):
    """Schemat do tworzenia kursu walut."""

    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


class ExchangeRateResponse(ExchangeRateBase):
    """Schemat odpowiedzi dla kursu walut."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    valid_from: datetime
    valid_to: Optional[datetime] = None
    is_active: bool = True
