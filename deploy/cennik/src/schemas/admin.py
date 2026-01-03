"""Schematy dla panelu administracyjnego - matryce cen."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..models.processing import GrindingProvider, FilmType


# === Grinding Matrix Schemas ===

class GrindingPriceCell(BaseModel):
    """Pojedyncza komórka matrycy szlifu."""

    id: Optional[int] = None
    price: float = Field(ge=0, description="Cena PLN/kg (0 = zablokowany)")
    is_blocked: bool = False
    grit: Optional[str] = None
    with_sb: bool = False


class GrindingMatrixResponse(BaseModel):
    """Odpowiedź z pełną matrycą cen szlifu."""

    provider: str
    width_variant: Optional[str] = None
    matrix: dict[float, dict[str, GrindingPriceCell]]
    thicknesses: list[float]
    grits: list[str]


class GrindingPriceUpdate(BaseModel):
    """Aktualizacja pojedynczej ceny szlifu."""

    thickness: float = Field(gt=0, description="Grubość w mm")
    grit: str = Field(description="Granulacja np. K320/K400")
    price: float = Field(description="Cena PLN/kg (>0=dostepny, 0=dziedzicz, <0=blokada)")
    width_variant: Optional[str] = None
    with_sb: bool = False


class GrindingBulkUpdateRequest(BaseModel):
    """Request do masowej aktualizacji matrycy."""

    updates: list[GrindingPriceUpdate]


class GrindingBulkUpdateResponse(BaseModel):
    """Odpowiedź z masowej aktualizacji."""

    updated: int
    provider: str


class AvailableProvidersResponse(BaseModel):
    """Odpowiedź z dostępnymi dostawcami szlifu."""

    providers: list[dict]
    thickness: float
    width: float


# === Film Matrix Schemas ===

class FilmPriceCell(BaseModel):
    """Pojedyncza komórka matrycy folii."""

    id: Optional[int] = None
    price: float = Field(ge=0, description="Cena PLN/kg")
    film_type: str


class FilmMatrixResponse(BaseModel):
    """Odpowiedź z matrycą cen folii."""

    matrix: dict[float, dict[str, FilmPriceCell]]
    thicknesses: list[float]
    film_types: list[str]


class FilmPriceUpdate(BaseModel):
    """Aktualizacja pojedynczej ceny folii."""

    thickness: float = Field(gt=0, description="Grubość w mm")
    film_type: FilmType
    price: float = Field(description="Cena PLN/kg (>0=dostepny, 0=dziedzicz, <0=blokada)")


class FilmBulkUpdateRequest(BaseModel):
    """Request do masowej aktualizacji matrycy folii."""

    updates: list[FilmPriceUpdate]


# === Initialization Schemas ===

class COSTAInitRequest(BaseModel):
    """Request do inicjalizacji cen COSTA."""

    copy_from: GrindingProvider = Field(
        default=GrindingProvider.BABCIA,
        description="Kopiuj ceny od innego dostawcy"
    )
    blocked_thickness_min: float = Field(
        default=0.0,
        description="Grubości poniżej tej wartości mają cenę 0"
    )
    blocked_thickness_max: float = Field(
        default=999.0,
        description="Grubości powyżej tej wartości mają cenę 0"
    )


class COSTAInitResponse(BaseModel):
    """Odpowiedź z inicjalizacji COSTA."""

    created: int
    blocked: int
    available: int


# === Import/Export Schemas ===

class MatrixExportRequest(BaseModel):
    """Request do eksportu matrycy."""

    provider: Optional[GrindingProvider] = None
    include_blocked: bool = True


class MatrixImportResult(BaseModel):
    """Wynik importu matrycy z Excela."""

    success: bool
    provider: str
    rows_processed: int
    rows_updated: int
    rows_created: int
    errors: list[str] = []


# === Validation Schemas ===

class GrindingAvailabilityCheck(BaseModel):
    """Request do sprawdzenia dostępności szlifu."""

    provider: GrindingProvider
    thickness: float
    width: float
    grit: str
    with_sb: bool = False


class GrindingAvailabilityResponse(BaseModel):
    """Odpowiedź z dostępności szlifu."""

    is_available: bool
    price: Optional[float] = None
    provider: str
    thickness: float
    grit: str
    reason: Optional[str] = None


# === Add Row/Column Schemas ===

class AddGrindingRowRequest(BaseModel):
    """Request do dodania nowego wiersza (grubosci) do matrycy szlifu."""

    thickness: float = Field(gt=0, description="Nowa grubosc w mm")
    default_price: float = Field(default=0, ge=0, description="Domyslna cena dla wszystkich granulacji")


class AddGrindingColumnRequest(BaseModel):
    """Request do dodania nowej kolumny (granulacji) do matrycy szlifu."""

    grit: str = Field(description="Nowa granulacja np. K500")
    with_sb: bool = Field(default=False, description="Czy z SB")
    default_price: float = Field(default=0, ge=0, description="Domyslna cena dla wszystkich grubosci")


class AddFilmRowRequest(BaseModel):
    """Request do dodania nowego wiersza (grubosci) do matrycy folii."""

    thickness: float = Field(gt=0, description="Nowa grubosc w mm")
    default_price: float = Field(default=0, ge=0, description="Domyslna cena dla wszystkich typow folii")


class AddMatrixResponse(BaseModel):
    """Odpowiedz z dodania wiersza/kolumny."""

    success: bool
    created: int
    message: str


# === Base Price Matrix Schemas ===

class BasePriceCell(BaseModel):
    """Pojedyncza komórka matrycy cen bazowych."""

    id: Optional[int] = None
    price: float = Field(ge=0, description="Cena PLN/kg")
    surface_finish: str
    material_id: int
    thickness: float
    width: float


class BasePriceMaterialRow(BaseModel):
    """Wiersz materiału w matrycy cen."""

    material_id: int
    grade: str
    name: str
    category: str
    group_name: Optional[str] = None
    prices: dict[str, BasePriceCell]  # klucz = surface_finish


class BasePriceMatrixResponse(BaseModel):
    """Odpowiedź z matrycą cen bazowych dla wybranej grubości/szerokości."""

    model_config = ConfigDict(from_attributes=True)

    thickness: float
    width: float
    surface_finishes: list[str]
    materials: list[BasePriceMaterialRow]


class BasePriceUpdate(BaseModel):
    """Aktualizacja pojedynczej ceny bazowej."""

    material_id: int
    surface_finish: str
    thickness: float
    width: float
    price: float = Field(ge=0, description="Cena PLN/kg")


class BasePriceBulkUpdateRequest(BaseModel):
    """Request do masowej aktualizacji cen bazowych."""

    updates: list[BasePriceUpdate]


class BasePriceBulkUpdateResponse(BaseModel):
    """Odpowiedź z masowej aktualizacji cen bazowych."""

    updated: int
    created: int


# === Bulk Price Change Schemas ===

class BulkPriceFilterRequest(BaseModel):
    """Filtry dla operacji zbiorczych zmian cen."""

    categories: Optional[list[str]] = Field(None, description="Lista kategorii (przyciski multi-select)")
    group_ids: Optional[list[int]] = Field(None, description="Lista ID grup materiałów (multi-select)")
    grades: Optional[list[str]] = Field(None, description="Lista gatunków (multi-select)")
    surface_finishes: Optional[list[str]] = Field(None, description="Lista wykończeń (przyciski multi-select)")
    thickness_min: Optional[float] = Field(None, ge=0, description="Minimalna grubość mm")
    thickness_max: Optional[float] = Field(None, ge=0, description="Maksymalna grubość mm")
    widths: Optional[list[float]] = Field(None, description="Lista szerokości mm (przyciski multi-select)")


class BulkPricePreviewItem(BaseModel):
    """Pojedyncza pozycja w podglądzie zmian."""

    id: int
    material_grade: str
    material_name: str
    group_name: Optional[str] = None
    surface_finish: str
    thickness: float
    width: float
    current_price: float
    new_price: float
    change_amount: float


class BulkPricePreviewResponse(BaseModel):
    """Odpowiedź z podglądem zmian zbiorczych."""

    total_affected: int
    total_current_value: float
    total_new_value: float
    change_type: str
    change_value: float
    items: list[BulkPricePreviewItem]
    page: int = 1
    per_page: int = 50
    total_pages: int = 1


class BulkPriceChangeRequest(BaseModel):
    """Request do zbiorczej zmiany cen."""

    filters: BulkPriceFilterRequest
    change_type: str = Field(description="Typ zmiany: 'percentage' lub 'absolute'")
    change_value: float = Field(description="Wartość zmiany: % lub PLN/kg")
    round_to: int = Field(default=2, ge=0, le=4, description="Zaokrąglenie do N miejsc po przecinku")


class BulkPriceChangeResponse(BaseModel):
    """Odpowiedź po zastosowaniu zmian zbiorczych."""

    success: bool
    updated_count: int
    skipped_count: int = 0
    total_previous: float
    total_new: float
    change_type: str
    change_value: float


class BulkFilterOptionsResponse(BaseModel):
    """Odpowiedź z dostępnymi opcjami filtrów."""

    categories: list[dict]
    groups: list[dict]
    grades: list[str]
    surface_finishes: list[str]
    thickness_range: dict
    widths: list[float]  # Lista dostępnych szerokości (przyciski)


# === Export/Import Schemas ===

class ExportFiltersRequest(BaseModel):
    """Filtry dla eksportu danych."""

    categories: Optional[list[str]] = Field(None, description="Lista kategorii materialow")
    thickness_min: Optional[float] = Field(None, ge=0, description="Minimalna grubosc mm")
    thickness_max: Optional[float] = Field(None, ge=0, description="Maksymalna grubosc mm")
    width_min: Optional[float] = Field(None, ge=0, description="Minimalna szerokosc mm")
    width_max: Optional[float] = Field(None, ge=0, description="Maksymalna szerokosc mm")
    surface_finishes: Optional[list[str]] = Field(None, description="Lista wykonczn powierzchni")
    providers: Optional[list[str]] = Field(None, description="Lista dostawcow szlifu")
    film_types: Optional[list[str]] = Field(None, description="Lista typow folii")
    only_active: bool = Field(True, description="Tylko aktywne ceny")


class ImportDiffItem(BaseModel):
    """Pojedyncza zmiana w imporcie."""

    row_number: int
    change_type: str = Field(description="added, updated, removed, error")
    data_type: str = Field(description="base_price, grinding, film")

    # Identyfikatory
    grade: Optional[str] = None
    surface_finish: Optional[str] = None
    thickness: Optional[float] = None
    width: Optional[float] = None
    provider: Optional[str] = None
    film_type: Optional[str] = None

    # Wartosci
    current_price: Optional[float] = None
    new_price: Optional[float] = None
    price_change: Optional[float] = None

    # Bledy
    error_message: Optional[str] = None


class ImportPreviewResponse(BaseModel):
    """Odpowiedz z podgladem importu."""

    import_id: str
    filename: str
    total_rows: int
    valid_rows: int
    error_rows: int

    added: int
    updated: int
    removed: int
    unchanged: int

    items: list[ImportDiffItem]
    page: int = 1
    per_page: int = 50
    total_pages: int = 1

    errors: list[dict] = []
    warnings: list[str] = []


class ImportApplyRequest(BaseModel):
    """Request do zastosowania importu."""

    mode: str = Field(
        description="Tryb importu: update_existing, add_new, full_sync"
    )
    confirm: bool = Field(
        default=False,
        description="Potwierdzenie importu"
    )


class ImportApplyResponse(BaseModel):
    """Odpowiedz po zastosowaniu importu."""

    success: bool
    import_id: str
    records_added: int
    records_updated: int
    records_skipped: int
    records_failed: int
    errors: list[dict] = []


class ExportHistoryItem(BaseModel):
    """Pojedynczy wpis historii eksportu."""

    id: int
    operation_type: str
    file_name: str
    file_type: str
    data_type: str
    records_count: int
    created_at: str
    status: str


class ImportExportHistoryResponse(BaseModel):
    """Odpowiedz z historia eksportu/importu."""

    items: list[ExportHistoryItem]
    total: int
    page: int = 1
    per_page: int = 20
