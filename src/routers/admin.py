"""Endpointy administracyjne - zarządzanie matrycami cen i materiałami."""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from io import BytesIO

from ..database import get_db
from ..models import (
    GrindingPrice,
    GrindingProvider,
    FilmPrice,
    FilmType,
    User,
    Material,
    MaterialGroup,
    MaterialCategory,
    SurfaceFinish,
)
from ..models.price import BasePrice
from ..auth.dependencies import get_current_user
from ..services import GrindingValidationService, BulkPricingService, PriceExporter, ExcelImporter
import tempfile
import os
import json
from ..schemas.admin import (
    GrindingMatrixResponse,
    GrindingPriceUpdate,
    GrindingBulkUpdateRequest,
    GrindingBulkUpdateResponse,
    AvailableProvidersResponse,
    FilmMatrixResponse,
    FilmPriceUpdate,
    FilmBulkUpdateRequest,
    COSTAInitRequest,
    COSTAInitResponse,
    GrindingAvailabilityCheck,
    GrindingAvailabilityResponse,
    AddGrindingRowRequest,
    AddGrindingColumnRequest,
    AddFilmRowRequest,
    AddMatrixResponse,
    BasePriceMatrixResponse,
    BasePriceMaterialRow,
    BasePriceCell,
    BasePriceUpdate,
    BasePriceBulkUpdateRequest,
    BasePriceBulkUpdateResponse,
    BulkPriceFilterRequest,
    BulkPricePreviewResponse,
    BulkPriceChangeRequest,
    BulkPriceChangeResponse,
    BulkFilterOptionsResponse,
    ExportFiltersRequest,
    ImportPreviewResponse,
    ImportApplyRequest,
    ImportApplyResponse,
    ImportExportHistoryResponse,
)
from ..schemas.pricing import (
    MaterialGroupCreate,
    MaterialGroupUpdate,
    MaterialGroupResponse,
    MaterialGroupWithMaterials,
    MaterialCreate,
    MaterialUpdate,
    MaterialResponse,
    MaterialWithGroup,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# === Grinding Matrix Endpoints ===

@router.get("/grinding-prices/matrix/{provider}", response_model=GrindingMatrixResponse)
async def get_grinding_matrix(
    provider: GrindingProvider,
    width_variant: Optional[str] = Query(None, description="Wariant szerokości dla BORYS"),
    db: Session = Depends(get_db),
):
    """Pobierz pełną matrycę cen szlifu (grubość x granulacja).

    Zwraca wszystkie grubości - te z ceną 0 są zablokowane.
    """
    service = GrindingValidationService(db)
    return service.get_grinding_matrix(provider, width_variant)


@router.put("/grinding-prices/matrix/{provider}/bulk", response_model=GrindingBulkUpdateResponse)
async def update_grinding_matrix_bulk(
    provider: GrindingProvider,
    request: GrindingBulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Masowa aktualizacja matrycy cen szlifu.

    Wpisanie ceny = 0 blokuje kombinację.
    Wpisanie ceny > 0 odblokowuje kombinację.
    """
    service = GrindingValidationService(db)
    count = service.bulk_update_matrix(provider, [u.model_dump() for u in request.updates])

    return GrindingBulkUpdateResponse(
        updated=count,
        provider=provider.value,
    )


@router.put("/grinding-prices/{price_id}")
async def update_grinding_price(
    price_id: int,
    price: float = Query(..., description="Cena PLN/kg (>0=dostepny, 0=dziedzicz, <0=blokada)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aktualizuj pojedynczą cenę szlifu.

    Do użycia z HTMX dla inline edycji w matrycy.
    """
    grinding_price = db.query(GrindingPrice).filter(GrindingPrice.id == price_id).first()

    if not grinding_price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    grinding_price.price_pln_per_kg = price
    db.commit()

    return {
        "id": grinding_price.id,
        "price": grinding_price.price_pln_per_kg,
        "is_blocked": grinding_price.price_pln_per_kg == 0,
    }


@router.get("/grinding-prices/available")
async def get_available_providers(
    thickness: float = Query(..., gt=0, description="Grubość blachy w mm"),
    width: float = Query(..., gt=0, description="Szerokość blachy w mm"),
    grit: Optional[str] = Query(None, description="Granulacja do filtrowania"),
    db: Session = Depends(get_db),
):
    """Pobierz dostępnych dostawców szlifu dla parametrów.

    Zwraca tylko te opcje gdzie cena > 0 w matrycy.
    """
    service = GrindingValidationService(db)
    providers = service.get_available_providers(thickness, width, grit)

    return {
        "providers": providers,
        "thickness": thickness,
        "width": width,
    }


@router.post("/grinding-prices/check", response_model=GrindingAvailabilityResponse)
async def check_grinding_availability(
    request: GrindingAvailabilityCheck,
    db: Session = Depends(get_db),
):
    """Sprawdź czy konkretna konfiguracja szlifu jest dostępna."""
    service = GrindingValidationService(db)
    is_available, price = service.is_grinding_available(
        provider=request.provider,
        thickness=request.thickness,
        width=request.width,
        grit=request.grit,
        with_sb=request.with_sb,
    )

    reason = None
    if not is_available:
        reason = "Kombinacja zablokowana w matrycy cen (cena = 0)"

    return GrindingAvailabilityResponse(
        is_available=is_available,
        price=price,
        provider=request.provider.value,
        thickness=request.thickness,
        grit=request.grit,
        reason=reason,
    )


@router.get("/grinding-prices/providers")
async def list_grinding_providers():
    """Lista wszystkich dostawców szlifu."""
    return {
        "providers": [
            {"value": p.value, "name": p.value}
            for p in GrindingProvider
        ]
    }


# === COSTA Initialization ===

@router.post("/grinding-prices/init-costa", response_model=COSTAInitResponse)
async def initialize_costa_prices(
    request: COSTAInitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Inicjalizuj matrycę cen dla COSTA.

    Kopiuje ceny od wybranego dostawcy (domyślnie BABCIA)
    i ustawia ceny = 0 dla grubości poza zakresem.
    """
    # Pobierz ceny źródłowe
    source_prices = db.query(GrindingPrice).filter(
        GrindingPrice.provider == request.copy_from,
        GrindingPrice.is_active == True,
    ).all()

    if not source_prices:
        raise HTTPException(
            status_code=404,
            detail=f"Brak cen dla dostawcy {request.copy_from.value}"
        )

    created = 0
    blocked = 0
    available = 0

    for source in source_prices:
        # Sprawdź czy kombinacja już istnieje
        existing = db.query(GrindingPrice).filter(
            GrindingPrice.provider == GrindingProvider.COSTA,
            GrindingPrice.thickness == source.thickness,
            GrindingPrice.grit == source.grit,
            GrindingPrice.width_variant == source.width_variant,
            GrindingPrice.with_sb == source.with_sb,
        ).first()

        if existing:
            continue

        # Określ czy grubość jest w dozwolonym zakresie
        in_range = (
            source.thickness >= request.blocked_thickness_min and
            source.thickness <= request.blocked_thickness_max
        )

        price = source.price_pln_per_kg if in_range else 0.0

        new_price = GrindingPrice(
            provider=GrindingProvider.COSTA,
            thickness=source.thickness,
            grit=source.grit,
            width_variant=source.width_variant,
            with_sb=source.with_sb,
            price_pln_per_kg=price,
            is_active=True,
        )
        db.add(new_price)
        created += 1

        if price > 0:
            available += 1
        else:
            blocked += 1

    db.commit()

    return COSTAInitResponse(
        created=created,
        blocked=blocked,
        available=available,
    )


# === Film Matrix Endpoints ===

@router.get("/film-prices/matrix", response_model=FilmMatrixResponse)
async def get_film_matrix(db: Session = Depends(get_db)):
    """Pobierz pełną matrycę cen folii (grubość x typ folii)."""
    prices = db.query(FilmPrice).filter(FilmPrice.is_active == True).all()

    matrix = {}
    thicknesses = set()
    film_types = set()

    for p in prices:
        thicknesses.add(p.thickness)
        film_types.add(p.film_type.value)

        if p.thickness not in matrix:
            matrix[p.thickness] = {}

        matrix[p.thickness][p.film_type.value] = {
            "id": p.id,
            "price": p.price_pln_per_kg,
            "film_type": p.film_type.value,
        }

    return FilmMatrixResponse(
        matrix=matrix,
        thicknesses=sorted(thicknesses),
        film_types=sorted(film_types),
    )


@router.put("/film-prices/{price_id}")
async def update_film_price(
    price_id: int,
    price: float = Query(..., description="Cena PLN/kg (>0=dostepny, 0=dziedzicz, <0=blokada)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aktualizuj pojedynczą cenę folii."""
    film_price = db.query(FilmPrice).filter(FilmPrice.id == price_id).first()

    if not film_price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    film_price.price_pln_per_kg = price
    db.commit()

    return {
        "id": film_price.id,
        "price": film_price.price_pln_per_kg,
        "film_type": film_price.film_type.value,
    }


@router.put("/film-prices/bulk")
async def update_film_matrix_bulk(
    request: FilmBulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Masowa aktualizacja matrycy cen folii."""
    count = 0

    for update in request.updates:
        existing = db.query(FilmPrice).filter(
            FilmPrice.thickness == update.thickness,
            FilmPrice.film_type == update.film_type,
        ).first()

        if existing:
            existing.price_pln_per_kg = update.price
        else:
            new_price = FilmPrice(
                thickness=update.thickness,
                film_type=update.film_type,
                price_pln_per_kg=update.price,
            )
            db.add(new_price)
        count += 1

    db.commit()

    return {"updated": count}


@router.get("/film-prices/types")
async def list_film_types():
    """Lista wszystkich typów folii."""
    return {
        "film_types": [
            {"value": f.value, "name": f.value}
            for f in FilmType
        ]
    }


# === Statistics ===

@router.get("/stats/grinding")
async def get_grinding_stats(db: Session = Depends(get_db)):
    """Statystyki matryc szlifu."""
    stats = {}

    for provider in GrindingProvider:
        total = db.query(GrindingPrice).filter(
            GrindingPrice.provider == provider
        ).count()

        available = db.query(GrindingPrice).filter(
            GrindingPrice.provider == provider,
            GrindingPrice.price_pln_per_kg > 0,
            GrindingPrice.is_active == True,
        ).count()

        blocked = db.query(GrindingPrice).filter(
            GrindingPrice.provider == provider,
            GrindingPrice.price_pln_per_kg == 0,
        ).count()

        stats[provider.value] = {
            "total": total,
            "available": available,
            "blocked": blocked,
        }

    return stats


# === Add Row/Column Endpoints ===

@router.post("/grinding-prices/matrix/{provider}/add-row", response_model=AddMatrixResponse)
async def add_grinding_row(
    provider: GrindingProvider,
    request: AddGrindingRowRequest,
    width_variant: Optional[str] = Query(None, description="Wariant szerokosci dla BORYS"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dodaj nowy wiersz (grubosc) do matrycy szlifu.

    Tworzy wpisy dla wszystkich istniejacych granulacji z podana cena.
    """
    # Pobierz istniejace granulacje dla tego dostawcy
    existing_grits = db.query(GrindingPrice.grit, GrindingPrice.with_sb).filter(
        GrindingPrice.provider == provider,
        GrindingPrice.is_active == True,
    ).distinct().all()

    if not existing_grits:
        raise HTTPException(
            status_code=400,
            detail="Brak istniejacych granulacji dla tego dostawcy"
        )

    # Sprawdz czy grubosc juz istnieje
    existing = db.query(GrindingPrice).filter(
        GrindingPrice.provider == provider,
        GrindingPrice.thickness == request.thickness,
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Grubosc {request.thickness} juz istnieje dla {provider.value}"
        )

    created = 0
    for grit, with_sb in existing_grits:
        new_price = GrindingPrice(
            provider=provider,
            thickness=request.thickness,
            grit=grit,
            with_sb=with_sb,
            width_variant=width_variant,
            price_pln_per_kg=request.default_price,
            is_active=True,
        )
        db.add(new_price)
        created += 1

    db.commit()

    return AddMatrixResponse(
        success=True,
        created=created,
        message=f"Dodano grubosc {request.thickness}mm z {created} wpisami"
    )


@router.post("/grinding-prices/matrix/{provider}/add-column", response_model=AddMatrixResponse)
async def add_grinding_column(
    provider: GrindingProvider,
    request: AddGrindingColumnRequest,
    width_variant: Optional[str] = Query(None, description="Wariant szerokosci dla BORYS"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dodaj nowa kolumne (granulacje) do matrycy szlifu.

    Tworzy wpisy dla wszystkich istniejacych grubosci z podana cena.
    """
    # Pobierz istniejace grubosci dla tego dostawcy
    existing_thicknesses = db.query(GrindingPrice.thickness).filter(
        GrindingPrice.provider == provider,
        GrindingPrice.is_active == True,
    ).distinct().all()

    if not existing_thicknesses:
        raise HTTPException(
            status_code=400,
            detail="Brak istniejacych grubosci dla tego dostawcy"
        )

    # Sprawdz czy granulacja juz istnieje
    existing = db.query(GrindingPrice).filter(
        GrindingPrice.provider == provider,
        GrindingPrice.grit == request.grit,
        GrindingPrice.with_sb == request.with_sb,
    ).first()

    if existing:
        suffix = " +SB" if request.with_sb else ""
        raise HTTPException(
            status_code=400,
            detail=f"Granulacja {request.grit}{suffix} juz istnieje dla {provider.value}"
        )

    created = 0
    for (thickness,) in existing_thicknesses:
        new_price = GrindingPrice(
            provider=provider,
            thickness=thickness,
            grit=request.grit,
            with_sb=request.with_sb,
            width_variant=width_variant,
            price_pln_per_kg=request.default_price,
            is_active=True,
        )
        db.add(new_price)
        created += 1

    db.commit()

    suffix = " +SB" if request.with_sb else ""
    return AddMatrixResponse(
        success=True,
        created=created,
        message=f"Dodano granulacje {request.grit}{suffix} z {created} wpisami"
    )


@router.post("/film-prices/add-row", response_model=AddMatrixResponse)
async def add_film_row(
    request: AddFilmRowRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dodaj nowy wiersz (grubosc) do matrycy folii.

    Tworzy wpisy dla wszystkich typow folii z podana cena.
    """
    # Sprawdz czy grubosc juz istnieje
    existing = db.query(FilmPrice).filter(
        FilmPrice.thickness == request.thickness,
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Grubosc {request.thickness} juz istnieje"
        )

    created = 0
    for film_type in FilmType:
        new_price = FilmPrice(
            film_type=film_type,
            thickness=request.thickness,
            price_pln_per_kg=request.default_price,
            is_active=True,
        )
        db.add(new_price)
        created += 1

    db.commit()

    return AddMatrixResponse(
        success=True,
        created=created,
        message=f"Dodano grubosc {request.thickness}mm z {created} wpisami"
    )


# === Material Groups Management ===

@router.get("/material-groups", response_model=list[MaterialGroupResponse])
async def list_material_groups(
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    include_inactive: bool = Query(False, description="Uwzględnij nieaktywne"),
    db: Session = Depends(get_db),
):
    """Pobierz listę grup materiałów."""
    query = db.query(MaterialGroup)

    if category:
        query = query.filter(MaterialGroup.category == category)

    if not include_inactive:
        query = query.filter(MaterialGroup.is_active == True)

    return query.order_by(MaterialGroup.category, MaterialGroup.display_order).all()


@router.get("/material-groups/{group_id}", response_model=MaterialGroupWithMaterials)
async def get_material_group(
    group_id: int,
    db: Session = Depends(get_db),
):
    """Pobierz grupę materiałów ze szczegółami."""
    group = db.query(MaterialGroup).options(
        joinedload(MaterialGroup.materials)
    ).filter(MaterialGroup.id == group_id).first()

    if not group:
        raise HTTPException(status_code=404, detail="Grupa nie znaleziona")

    return group


@router.post("/material-groups", response_model=MaterialGroupResponse, status_code=201)
async def create_material_group(
    data: MaterialGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Utwórz nową grupę materiałów."""
    existing = db.query(MaterialGroup).filter(MaterialGroup.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Grupa o tej nazwie już istnieje")

    group = MaterialGroup(**data.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)

    return group


@router.put("/material-groups/{group_id}", response_model=MaterialGroupResponse)
async def update_material_group(
    group_id: int,
    data: MaterialGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aktualizuj grupę materiałów."""
    group = db.query(MaterialGroup).filter(MaterialGroup.id == group_id).first()

    if not group:
        raise HTTPException(status_code=404, detail="Grupa nie znaleziona")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)

    db.commit()
    db.refresh(group)

    return group


@router.delete("/material-groups/{group_id}", status_code=204)
async def delete_material_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Usuń grupę materiałów (soft delete - ustawia is_active=False)."""
    group = db.query(MaterialGroup).filter(MaterialGroup.id == group_id).first()

    if not group:
        raise HTTPException(status_code=404, detail="Grupa nie znaleziona")

    # Soft delete - materiały zostają, ale tracą przypisanie
    group.is_active = False
    db.commit()


# === Materials Management ===

@router.get("/materials", response_model=list[MaterialWithGroup])
async def list_materials_admin(
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    group_id: Optional[int] = Query(None, description="Filtruj po grupie"),
    include_inactive: bool = Query(False, description="Uwzględnij nieaktywne"),
    db: Session = Depends(get_db),
):
    """Pobierz listę materiałów (widok admin)."""
    query = db.query(Material).options(joinedload(Material.group))

    if category:
        query = query.filter(Material.category == category)

    if group_id:
        query = query.filter(Material.group_id == group_id)

    if not include_inactive:
        query = query.filter(Material.is_active == True)

    return query.order_by(Material.category, Material.display_order, Material.grade).all()


@router.get("/materials/stats")
async def get_materials_stats(db: Session = Depends(get_db)):
    """Statystyki materiałów i grup."""
    stats = {
        "total_groups": db.query(MaterialGroup).filter(MaterialGroup.is_active == True).count(),
        "total_materials": db.query(Material).filter(Material.is_active == True).count(),
        "by_category": {},
    }

    for category in MaterialCategory:
        groups_count = db.query(MaterialGroup).filter(
            MaterialGroup.category == category,
            MaterialGroup.is_active == True,
        ).count()

        materials_count = db.query(Material).filter(
            Material.category == category,
            Material.is_active == True,
        ).count()

        stats["by_category"][category.value] = {
            "groups": groups_count,
            "materials": materials_count,
        }

    return stats


@router.get("/materials/{material_id}", response_model=MaterialWithGroup)
async def get_material_admin(
    material_id: int,
    db: Session = Depends(get_db),
):
    """Pobierz szczegóły materiału (widok admin)."""
    material = db.query(Material).options(
        joinedload(Material.group)
    ).filter(Material.id == material_id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Materiał nie znaleziony")

    return material


@router.post("/materials", response_model=MaterialResponse, status_code=201)
async def create_material_admin(
    data: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Utwórz nowy materiał."""
    existing = db.query(Material).filter(Material.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Materiał o tej nazwie już istnieje")

    # Walidacja group_id
    if data.group_id:
        group = db.query(MaterialGroup).filter(MaterialGroup.id == data.group_id).first()
        if not group:
            raise HTTPException(status_code=400, detail="Podana grupa nie istnieje")

    material = Material(**data.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)

    return material


@router.put("/materials/{material_id}", response_model=MaterialResponse)
async def update_material_admin(
    material_id: int,
    data: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aktualizuj materiał."""
    material = db.query(Material).filter(Material.id == material_id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Materiał nie znaleziony")

    # Walidacja group_id jeśli podano
    if data.group_id is not None and data.group_id != 0:
        group = db.query(MaterialGroup).filter(MaterialGroup.id == data.group_id).first()
        if not group:
            raise HTTPException(status_code=400, detail="Podana grupa nie istnieje")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(material, field, value)

    db.commit()
    db.refresh(material)

    return material


@router.delete("/materials/{material_id}", status_code=204)
async def delete_material_admin(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Usuń materiał (soft delete - ustawia is_active=False)."""
    material = db.query(Material).filter(Material.id == material_id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Materiał nie znaleziony")

    material.is_active = False
    db.commit()


@router.get("/categories")
async def list_categories():
    """Lista wszystkich kategorii materiałów."""
    return {
        "categories": [
            {"value": c.value, "name": c.name}
            for c in MaterialCategory
        ]
    }


# === Base Price Matrix Endpoints ===

@router.get("/base-prices/dimensions")
async def get_available_dimensions(
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    db: Session = Depends(get_db),
):
    """Pobierz dostępne wymiary (grubość x szerokość) dla cen bazowych."""
    query = db.query(
        BasePrice.thickness,
        BasePrice.width,
    ).distinct()

    if category:
        query = query.join(Material).filter(Material.category == category)

    dimensions = query.order_by(BasePrice.thickness, BasePrice.width).all()

    thicknesses = sorted(set(d.thickness for d in dimensions))
    widths = sorted(set(d.width for d in dimensions))

    return {
        "thicknesses": thicknesses,
        "widths": widths,
        "combinations": [{"thickness": d.thickness, "width": d.width} for d in dimensions],
    }


@router.get("/base-prices/surface-finishes")
async def get_surface_finishes(
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
):
    """Pobierz dostępne wykończenia powierzchni."""
    finishes = []

    if category == MaterialCategory.STAINLESS_STEEL or category is None:
        finishes.extend([
            SurfaceFinish.FINISH_2B,
            SurfaceFinish.FINISH_BA,
            SurfaceFinish.FINISH_1D,
            SurfaceFinish.FINISH_LEN,
            SurfaceFinish.FINISH_RYFEL,
        ])

    if category == MaterialCategory.CARBON_STEEL or category is None:
        finishes.extend([
            SurfaceFinish.FINISH_HR,
            SurfaceFinish.FINISH_CR,
            SurfaceFinish.FINISH_PICKLED,
            SurfaceFinish.FINISH_OILED,
        ])

    if category == MaterialCategory.ALUMINUM or category is None:
        finishes.extend([
            SurfaceFinish.FINISH_MILL,
            SurfaceFinish.FINISH_ANODIZED,
        ])

    return {
        "surface_finishes": [{"value": f.value, "name": f.value} for f in finishes],
    }


@router.get("/base-prices/matrix", response_model=BasePriceMatrixResponse)
async def get_base_price_matrix(
    thickness: float = Query(..., gt=0, description="Grubość w mm"),
    width: float = Query(..., gt=0, description="Szerokość w mm"),
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    db: Session = Depends(get_db),
):
    """Pobierz matrycę cen bazowych dla wybranej grubości i szerokości.

    Wiersze = materiały (gatunki), kolumny = wykończenia powierzchni.
    """
    # Pobierz materiały
    materials_query = db.query(Material).options(
        joinedload(Material.group)
    ).filter(Material.is_active == True)

    if category:
        materials_query = materials_query.filter(Material.category == category)

    materials = materials_query.order_by(
        Material.category, Material.display_order, Material.grade
    ).all()

    # Pobierz ceny dla tej grubości/szerokości
    prices_query = db.query(BasePrice).filter(
        BasePrice.thickness == thickness,
        BasePrice.width == width,
        BasePrice.is_active == True,
    )

    if category:
        prices_query = prices_query.join(Material).filter(Material.category == category)

    prices = prices_query.all()

    # Buduj mapę cen: material_id -> surface_finish -> price
    price_map = {}
    surface_finishes_set = set()

    for p in prices:
        if p.material_id not in price_map:
            price_map[p.material_id] = {}
        price_map[p.material_id][p.surface_finish] = p
        surface_finishes_set.add(p.surface_finish)

    # Określ dostępne wykończenia dla kategorii
    if category == MaterialCategory.STAINLESS_STEEL:
        surface_finishes = ["2B", "BA", "1D", "LEN", "RYFEL ASTM"]
    elif category == MaterialCategory.CARBON_STEEL:
        surface_finishes = ["HR", "CR", "trawiona", "naoliwiona"]
    elif category == MaterialCategory.ALUMINUM:
        surface_finishes = ["mill", "anodowana"]
    else:
        # Bez filtra kategorii - określ wykończenia na podstawie kategorii materiałów
        categories_present = set(mat.category for mat in materials)
        surface_finishes = []
        if MaterialCategory.STAINLESS_STEEL in categories_present:
            surface_finishes.extend(["2B", "BA", "1D", "LEN", "RYFEL ASTM"])
        if MaterialCategory.CARBON_STEEL in categories_present:
            surface_finishes.extend(["HR", "CR", "trawiona", "naoliwiona"])
        if MaterialCategory.ALUMINUM in categories_present:
            surface_finishes.extend(["mill", "anodowana"])
        if not surface_finishes:
            surface_finishes = sorted(surface_finishes_set)

    # Buduj wiersze materiałów
    material_rows = []
    for mat in materials:
        prices_dict = {}
        for sf in surface_finishes:
            if mat.id in price_map and sf in price_map[mat.id]:
                p = price_map[mat.id][sf]
                prices_dict[sf] = BasePriceCell(
                    id=p.id,
                    price=p.price_pln_per_kg,
                    surface_finish=sf,
                    material_id=mat.id,
                    thickness=thickness,
                    width=width,
                )
            else:
                prices_dict[sf] = BasePriceCell(
                    id=None,
                    price=0.0,
                    surface_finish=sf,
                    material_id=mat.id,
                    thickness=thickness,
                    width=width,
                )

        material_rows.append(BasePriceMaterialRow(
            material_id=mat.id,
            grade=mat.grade,
            name=mat.name,
            category=mat.category.value,
            group_name=mat.group.name if mat.group else None,
            prices=prices_dict,
        ))

    return BasePriceMatrixResponse(
        thickness=thickness,
        width=width,
        surface_finishes=surface_finishes,
        materials=material_rows,
    )


@router.put("/base-prices/{price_id}")
async def update_base_price(
    price_id: int,
    price: float = Query(..., ge=0, description="Cena PLN/kg"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aktualizuj pojedynczą cenę bazową."""
    base_price = db.query(BasePrice).filter(BasePrice.id == price_id).first()

    if not base_price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    base_price.price_pln_per_kg = price
    db.commit()

    return {
        "id": base_price.id,
        "price": base_price.price_pln_per_kg,
        "material_id": base_price.material_id,
        "surface_finish": base_price.surface_finish,
    }


@router.post("/base-prices", status_code=201)
async def create_base_price(
    data: BasePriceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Utwórz nową cenę bazową."""
    # Sprawdź czy materiał istnieje
    material = db.query(Material).filter(Material.id == data.material_id).first()
    if not material:
        raise HTTPException(status_code=400, detail="Materiał nie istnieje")

    # Sprawdź czy cena już istnieje
    existing = db.query(BasePrice).filter(
        BasePrice.material_id == data.material_id,
        BasePrice.surface_finish == data.surface_finish,
        BasePrice.thickness == data.thickness,
        BasePrice.width == data.width,
    ).first()

    if existing:
        # Aktualizuj istniejącą
        existing.price_pln_per_kg = data.price
        db.commit()
        return {
            "id": existing.id,
            "price": existing.price_pln_per_kg,
            "created": False,
        }

    # Utwórz nową
    base_price = BasePrice(
        material_id=data.material_id,
        surface_finish=data.surface_finish,
        thickness=data.thickness,
        width=data.width,
        length=data.width * 2,  # Domyślna długość
        price_pln_per_kg=data.price,
    )
    db.add(base_price)
    db.commit()
    db.refresh(base_price)

    return {
        "id": base_price.id,
        "price": base_price.price_pln_per_kg,
        "created": True,
    }


@router.post("/base-prices/add-surface-finish")
async def add_surface_finish_to_matrix(
    surface_finish: str = Query(..., description="Nowa powierzchnia (np. 2B, BA)"),
    category: str = Query(..., description="Kategoria materiału"),
    thickness: float = Query(..., description="Grubość"),
    width: float = Query(..., description="Szerokość"),
    default_price: float = Query(0, description="Domyślna cena PLN/kg"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dodaj nową powierzchnię do matrycy cen bazowych."""
    # Pobierz materiały z kategorii
    materials = db.query(Material).filter(Material.category == category).all()
    if not materials:
        raise HTTPException(status_code=400, detail="Brak materiałów w kategorii")

    created = 0
    skipped = 0

    for mat in materials:
        # Sprawdź czy już istnieje
        existing = db.query(BasePrice).filter(
            BasePrice.material_id == mat.id,
            BasePrice.surface_finish == surface_finish,
            BasePrice.thickness == thickness,
            BasePrice.width == width,
        ).first()

        if existing:
            skipped += 1
            continue

        # Utwórz nową cenę
        bp = BasePrice(
            material_id=mat.id,
            surface_finish=surface_finish,
            thickness=thickness,
            width=width,
            length=width * 2,
            price_pln_per_kg=default_price,
        )
        db.add(bp)
        created += 1

    db.commit()

    return {
        "message": f"Dodano powierzchnię '{surface_finish}'",
        "created": created,
        "skipped": skipped,
    }


@router.post("/base-prices/add-thickness")
async def add_thickness_to_matrix(
    new_thickness: float = Query(..., alias="thickness", description="Nowa grubość"),
    category: str = Query(..., description="Kategoria materiału"),
    width: float = Query(..., description="Szerokość"),
    default_price: float = Query(0, description="Domyślna cena PLN/kg"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dodaj nową grubość do matrycy cen bazowych."""
    # Pobierz materiały z kategorii
    materials = db.query(Material).filter(Material.category == category).all()
    if not materials:
        raise HTTPException(status_code=400, detail="Brak materiałów w kategorii")

    # Pobierz istniejące powierzchnie dla kategorii
    surface_finishes = db.query(BasePrice.surface_finish).join(Material).filter(
        Material.category == category
    ).distinct().all()
    surface_finishes = [sf[0] for sf in surface_finishes]

    if not surface_finishes:
        surface_finishes = ["2B"]  # Domyślna powierzchnia

    created = 0
    skipped = 0

    for mat in materials:
        for sf in surface_finishes:
            # Sprawdź czy już istnieje
            existing = db.query(BasePrice).filter(
                BasePrice.material_id == mat.id,
                BasePrice.surface_finish == sf,
                BasePrice.thickness == new_thickness,
                BasePrice.width == width,
            ).first()

            if existing:
                skipped += 1
                continue

            # Utwórz nową cenę
            bp = BasePrice(
                material_id=mat.id,
                surface_finish=sf,
                thickness=new_thickness,
                width=width,
                length=width * 2,
                price_pln_per_kg=default_price,
            )
            db.add(bp)
            created += 1

    db.commit()

    return {
        "message": f"Dodano grubość {new_thickness}mm",
        "created": created,
        "skipped": skipped,
    }


@router.post("/base-prices/add-width")
async def add_width_to_matrix(
    new_width: float = Query(..., alias="width", description="Nowa szerokość"),
    category: str = Query(..., description="Kategoria materiału"),
    thickness: float = Query(..., description="Grubość"),
    default_price: float = Query(0, description="Domyślna cena PLN/kg"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dodaj nową szerokość do matrycy cen bazowych."""
    # Pobierz materiały z kategorii
    materials = db.query(Material).filter(Material.category == category).all()
    if not materials:
        raise HTTPException(status_code=400, detail="Brak materiałów w kategorii")

    # Pobierz istniejące powierzchnie dla kategorii
    surface_finishes = db.query(BasePrice.surface_finish).join(Material).filter(
        Material.category == category
    ).distinct().all()
    surface_finishes = [sf[0] for sf in surface_finishes]

    if not surface_finishes:
        surface_finishes = ["2B"]  # Domyślna powierzchnia

    created = 0
    skipped = 0

    for mat in materials:
        for sf in surface_finishes:
            # Sprawdź czy już istnieje
            existing = db.query(BasePrice).filter(
                BasePrice.material_id == mat.id,
                BasePrice.surface_finish == sf,
                BasePrice.thickness == thickness,
                BasePrice.width == new_width,
            ).first()

            if existing:
                skipped += 1
                continue

            # Utwórz nową cenę
            bp = BasePrice(
                material_id=mat.id,
                surface_finish=sf,
                thickness=thickness,
                width=new_width,
                length=new_width * 2,
                price_pln_per_kg=default_price,
            )
            db.add(bp)
            created += 1

    db.commit()

    return {
        "message": f"Dodano szerokość {new_width}mm",
        "created": created,
        "skipped": skipped,
    }


@router.put("/base-prices/bulk", response_model=BasePriceBulkUpdateResponse)
async def update_base_prices_bulk(
    request: BasePriceBulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Masowa aktualizacja/tworzenie cen bazowych."""
    updated = 0
    created = 0

    for update in request.updates:
        existing = db.query(BasePrice).filter(
            BasePrice.material_id == update.material_id,
            BasePrice.surface_finish == update.surface_finish,
            BasePrice.thickness == update.thickness,
            BasePrice.width == update.width,
        ).first()

        if existing:
            existing.price_pln_per_kg = update.price
            updated += 1
        else:
            base_price = BasePrice(
                material_id=update.material_id,
                surface_finish=update.surface_finish,
                thickness=update.thickness,
                width=update.width,
                length=update.width * 2,
                price_pln_per_kg=update.price,
            )
            db.add(base_price)
            created += 1

    db.commit()

    return BasePriceBulkUpdateResponse(updated=updated, created=created)


@router.get("/base-prices/stats")
async def get_base_prices_stats(
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    db: Session = Depends(get_db),
):
    """Statystyki cen bazowych."""
    query = db.query(BasePrice).filter(BasePrice.is_active == True)

    if category:
        query = query.join(Material).filter(Material.category == category)

    total = query.count()
    with_price = query.filter(BasePrice.price_pln_per_kg > 0).count()

    # Statystyki per kategoria
    by_category = {}
    for cat in MaterialCategory:
        cat_query = db.query(BasePrice).join(Material).filter(
            Material.category == cat,
            BasePrice.is_active == True,
        )
        cat_total = cat_query.count()
        cat_with_price = cat_query.filter(BasePrice.price_pln_per_kg > 0).count()

        by_category[cat.value] = {
            "total": cat_total,
            "with_price": cat_with_price,
            "without_price": cat_total - cat_with_price,
        }

    return {
        "total": total,
        "with_price": with_price,
        "without_price": total - with_price,
        "by_category": by_category,
    }


# === Bulk Price Change Endpoints ===

@router.get("/base-prices/filter-options", response_model=BulkFilterOptionsResponse)
async def get_bulk_filter_options(
    category: Optional[str] = Query(None, description="Filtruj opcje po kategorii (deprecated)"),
    categories: Optional[str] = Query(None, description="Kategorie oddzielone przecinkiem"),
    group_ids: Optional[str] = Query(None, description="ID grup oddzielone przecinkiem"),
    grades: Optional[str] = Query(None, description="Gatunki oddzielone przecinkiem"),
    surface_finishes: Optional[str] = Query(None, description="Wykończenia oddzielone przecinkiem"),
    widths: Optional[str] = Query(None, description="Szerokości oddzielone przecinkiem"),
    db: Session = Depends(get_db),
):
    """Pobierz dostępne opcje filtrów - dwukierunkowe filtrowanie."""
    # Parse categories
    categories_list = None
    if categories:
        categories_list = [c.strip() for c in categories.split(",") if c.strip()]
    elif category:
        categories_list = [category]

    # Parse group_ids
    group_ids_list = None
    if group_ids:
        group_ids_list = [int(g.strip()) for g in group_ids.split(",") if g.strip()]

    # Parse grades
    grades_list = None
    if grades:
        grades_list = [g.strip() for g in grades.split(",") if g.strip()]

    # Parse surface_finishes
    surface_finishes_list = None
    if surface_finishes:
        surface_finishes_list = [s.strip() for s in surface_finishes.split(",") if s.strip()]

    # Parse widths
    widths_list = None
    if widths:
        widths_list = [float(w.strip()) for w in widths.split(",") if w.strip()]

    service = BulkPricingService(db)
    return service.get_filter_options(
        categories_list, group_ids_list, grades_list, surface_finishes_list, widths_list
    )


@router.post("/base-prices/bulk-change/preview", response_model=BulkPricePreviewResponse)
async def preview_bulk_price_change(
    request: BulkPriceChangeRequest,
    page: int = Query(1, ge=1, description="Numer strony"),
    per_page: int = Query(50, ge=10, le=200, description="Elementów na stronę"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Podgląd zbiorczej zmiany cen bez zapisywania.

    Zwraca listę cen, które zostaną zmienione wraz z nowymi wartościami.
    """
    service = BulkPricingService(db)
    return service.preview_changes(
        filters=request.filters,
        change_type=request.change_type,
        change_value=request.change_value,
        page=page,
        per_page=per_page,
        round_to=request.round_to,
    )


@router.post("/base-prices/bulk-change/apply", response_model=BulkPriceChangeResponse)
async def apply_bulk_price_change(
    request: BulkPriceChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Zastosuj zbiorczą zmianę cen.

    Zmienia ceny dla wszystkich pozycji pasujących do filtrów.
    Tworzy wpis w historii zmian (audit log).
    """
    service = BulkPricingService(db)
    return service.apply_changes(
        filters=request.filters,
        change_type=request.change_type,
        change_value=request.change_value,
        user=current_user,
        round_to=request.round_to,
    )


@router.get("/base-prices/audit-history")
async def get_price_audit_history(
    limit: int = Query(50, ge=1, le=200, description="Limit wyników"),
    offset: int = Query(0, ge=0, description="Offset dla paginacji"),
    change_type: Optional[str] = Query(None, description="Filtruj po typie zmiany"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pobierz historię zmian cen."""
    service = BulkPricingService(db)
    return service.get_audit_history(
        limit=limit,
        offset=offset,
        change_type=change_type,
    )


# === Export Endpoints ===

@router.get("/export/base-prices")
async def export_base_prices(
    format: str = Query("xlsx", description="Format eksportu: xlsx lub csv"),
    categories: Optional[str] = Query(None, description="Kategorie oddzielone przecinkiem"),
    thickness_min: Optional[float] = Query(None, description="Minimalna grubosc"),
    thickness_max: Optional[float] = Query(None, description="Maksymalna grubosc"),
    width_min: Optional[float] = Query(None, description="Minimalna szerokosc"),
    width_max: Optional[float] = Query(None, description="Maksymalna szerokosc"),
    surface_finishes: Optional[str] = Query(None, description="Wykoncznie oddzielone przecinkiem"),
    only_active: bool = Query(True, description="Tylko aktywne ceny"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eksportuj ceny bazowe do Excel lub CSV."""
    exporter = PriceExporter(db)

    # Parse parametrow
    categories_list = [c.strip() for c in categories.split(",")] if categories else None
    surface_list = [s.strip() for s in surface_finishes.split(",")] if surface_finishes else None

    if format == "csv":
        content = exporter.export_base_prices_csv(
            categories=categories_list,
            thickness_min=thickness_min,
            thickness_max=thickness_max,
            surface_finishes=surface_list,
            only_active=only_active,
        )
        filename = exporter.get_export_filename("base_prices", "csv")
        return StreamingResponse(
            BytesIO(content.encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        content = exporter.export_base_prices(
            categories=categories_list,
            thickness_min=thickness_min,
            thickness_max=thickness_max,
            width_min=width_min,
            width_max=width_max,
            surface_finishes=surface_list,
            only_active=only_active,
        )
        filename = exporter.get_export_filename("base_prices", "xlsx")
        return StreamingResponse(
            BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.get("/export/grinding")
async def export_grinding_prices(
    format: str = Query("xlsx", description="Format eksportu: xlsx"),
    providers: Optional[str] = Query(None, description="Dostawcy oddzieleni przecinkiem"),
    thickness_min: Optional[float] = Query(None, description="Minimalna grubosc"),
    thickness_max: Optional[float] = Query(None, description="Maksymalna grubosc"),
    only_active: bool = Query(True, description="Tylko aktywne ceny"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eksportuj cennik szlifu do Excel."""
    exporter = PriceExporter(db)

    providers_list = [p.strip() for p in providers.split(",")] if providers else None

    content = exporter.export_grinding_prices(
        providers=providers_list,
        thickness_min=thickness_min,
        thickness_max=thickness_max,
        only_active=only_active,
    )

    filename = exporter.get_export_filename("grinding", "xlsx")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/film")
async def export_film_prices(
    format: str = Query("xlsx", description="Format eksportu: xlsx"),
    film_types: Optional[str] = Query(None, description="Typy folii oddzielone przecinkiem"),
    thickness_min: Optional[float] = Query(None, description="Minimalna grubosc"),
    thickness_max: Optional[float] = Query(None, description="Maksymalna grubosc"),
    only_active: bool = Query(True, description="Tylko aktywne ceny"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eksportuj cennik folii do Excel."""
    exporter = PriceExporter(db)

    film_types_list = [f.strip() for f in film_types.split(",")] if film_types else None

    content = exporter.export_film_prices(
        film_types=film_types_list,
        thickness_min=thickness_min,
        thickness_max=thickness_max,
        only_active=only_active,
    )

    filename = exporter.get_export_filename("film", "xlsx")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/modifiers")
async def export_modifiers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eksportuj modyfikatory cen do Excel."""
    exporter = PriceExporter(db)

    content = exporter.export_modifiers()

    filename = exporter.get_export_filename("modifiers", "xlsx")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/all")
async def export_all_prices(
    categories: Optional[str] = Query(None, description="Kategorie oddzielone przecinkiem"),
    thickness_min: Optional[float] = Query(None, description="Minimalna grubosc"),
    thickness_max: Optional[float] = Query(None, description="Maksymalna grubosc"),
    surface_finishes: Optional[str] = Query(None, description="Wykoncznie oddzielone przecinkiem"),
    only_active: bool = Query(True, description="Tylko aktywne ceny"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eksportuj wszystkie ceny do wieloarkuszowego Excela."""
    exporter = PriceExporter(db)

    categories_list = [c.strip() for c in categories.split(",")] if categories else None
    surface_list = [s.strip() for s in surface_finishes.split(",")] if surface_finishes else None

    content = exporter.export_all(
        categories=categories_list,
        thickness_min=thickness_min,
        thickness_max=thickness_max,
        surface_finishes=surface_list,
        only_active=only_active,
    )

    filename = exporter.get_export_filename("all", "xlsx")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# === Import Endpoints ===

# Tymczasowe przechowywanie analiz importu (w produkcji uzyc Redis/DB)
_import_cache: dict = {}


@router.post("/import/upload", response_model=ImportPreviewResponse)
async def upload_import_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload pliku do importu i wygeneruj podglad zmian.

    Zwraca import_id do uzycia w kolejnych krokach.
    """
    # Walidacja typu pliku
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Tylko pliki Excel (.xlsx, .xls) sa akceptowane"
        )

    # Zapisz plik tymczasowo
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Analizuj plik
        from pathlib import Path
        importer = ExcelImporter(db)
        analysis = importer.analyze_file(Path(tmp_path))

        # Zapisz analize do cache
        _import_cache[analysis.import_id] = {
            "analysis": analysis,
            "filename": file.filename,
            "created_at": datetime.now().isoformat(),
        }

        # Przygotuj odpowiedz
        items = [
            {
                "row_number": item.row_number,
                "change_type": item.change_type,
                "data_type": item.data_type,
                "grade": item.grade,
                "surface_finish": item.surface_finish,
                "thickness": item.thickness,
                "width": item.width,
                "provider": item.provider,
                "film_type": item.film_type,
                "current_price": item.current_price,
                "new_price": item.new_price,
                "price_change": item.price_change,
                "error_message": item.error_message,
            }
            for item in analysis.items[:50]  # Pierwsze 50 zmian
        ]

        return ImportPreviewResponse(
            import_id=analysis.import_id,
            filename=file.filename,
            total_rows=analysis.total_rows,
            valid_rows=analysis.valid_rows,
            error_rows=analysis.error_rows,
            added=analysis.added,
            updated=analysis.updated,
            removed=analysis.removed,
            unchanged=analysis.unchanged,
            items=items,
            page=1,
            per_page=50,
            total_pages=(len(analysis.items) + 49) // 50,
            errors=analysis.errors,
            warnings=analysis.warnings,
        )

    finally:
        # Usun plik tymczasowy
        os.unlink(tmp_path)


@router.get("/import/{import_id}/preview", response_model=ImportPreviewResponse)
async def get_import_preview(
    import_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pobierz podglad zmian dla importu z paginacja."""
    if import_id not in _import_cache:
        raise HTTPException(status_code=404, detail="Import nie znaleziony")

    cached = _import_cache[import_id]
    analysis = cached["analysis"]

    # Paginacja
    start = (page - 1) * per_page
    end = start + per_page
    items = [
        {
            "row_number": item.row_number,
            "change_type": item.change_type,
            "data_type": item.data_type,
            "grade": item.grade,
            "surface_finish": item.surface_finish,
            "thickness": item.thickness,
            "width": item.width,
            "provider": item.provider,
            "film_type": item.film_type,
            "current_price": item.current_price,
            "new_price": item.new_price,
            "price_change": item.price_change,
            "error_message": item.error_message,
        }
        for item in analysis.items[start:end]
    ]

    return ImportPreviewResponse(
        import_id=analysis.import_id,
        filename=cached["filename"],
        total_rows=analysis.total_rows,
        valid_rows=analysis.valid_rows,
        error_rows=analysis.error_rows,
        added=analysis.added,
        updated=analysis.updated,
        removed=analysis.removed,
        unchanged=analysis.unchanged,
        items=items,
        page=page,
        per_page=per_page,
        total_pages=(len(analysis.items) + per_page - 1) // per_page,
        errors=analysis.errors,
        warnings=analysis.warnings,
    )


@router.post("/import/{import_id}/apply", response_model=ImportApplyResponse)
async def apply_import(
    import_id: str,
    request: ImportApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Zastosuj import ze wskazanym trybem."""
    if import_id not in _import_cache:
        raise HTTPException(status_code=404, detail="Import nie znaleziony")

    if not request.confirm:
        raise HTTPException(status_code=400, detail="Wymagane potwierdzenie importu")

    cached = _import_cache[import_id]
    analysis = cached["analysis"]

    # Zastosuj import
    importer = ExcelImporter(db)
    result = importer.apply_import(analysis, mode=request.mode)

    # Zapisz do audytu
    from ..models.price import ImportExportAudit
    audit = ImportExportAudit(
        operation_type="import",
        file_name=cached["filename"],
        file_type="xlsx",
        data_type="all",
        filters_json=json.dumps({"mode": request.mode}),
        records_count=analysis.total_rows,
        records_added=result.base_prices_imported + result.grinding_prices_imported + result.film_prices_imported,
        records_updated=analysis.updated if result.success else 0,
        records_skipped=analysis.unchanged,
        user_id=current_user.id,
        status="success" if result.success else "failed",
        error_message=json.dumps(result.errors) if result.errors else None,
    )
    db.add(audit)
    db.commit()

    # Usun z cache
    del _import_cache[import_id]

    return ImportApplyResponse(
        success=result.success,
        import_id=import_id,
        records_added=result.base_prices_imported + result.grinding_prices_imported + result.film_prices_imported,
        records_updated=analysis.updated,
        records_skipped=analysis.unchanged,
        records_failed=len(result.errors),
        errors=result.errors,
    )


@router.delete("/import/{import_id}")
async def cancel_import(
    import_id: str,
    current_user: User = Depends(get_current_user),
):
    """Anuluj import i usun tymczasowe dane."""
    if import_id not in _import_cache:
        raise HTTPException(status_code=404, detail="Import nie znaleziony")

    del _import_cache[import_id]

    return {"success": True, "message": "Import anulowany"}


@router.get("/import-export/history", response_model=ImportExportHistoryResponse)
async def get_import_export_history(
    operation_type: Optional[str] = Query(None, description="Filtruj: import lub export"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pobierz historie operacji importu/eksportu."""
    from ..models.price import ImportExportAudit

    query = db.query(ImportExportAudit)

    if operation_type:
        query = query.filter(ImportExportAudit.operation_type == operation_type)

    total = query.count()
    items = query.order_by(ImportExportAudit.created_at.desc()).offset(offset).limit(limit).all()

    return ImportExportHistoryResponse(
        items=[
            {
                "id": item.id,
                "operation_type": item.operation_type,
                "file_name": item.file_name,
                "file_type": item.file_type,
                "data_type": item.data_type,
                "records_count": item.records_count,
                "created_at": item.created_at.isoformat(),
                "status": item.status,
            }
            for item in items
        ],
        total=total,
        page=(offset // limit) + 1,
        per_page=limit,
    )


# === Price History Endpoints ===

@router.get("/price-history")
async def get_price_history(
    category: Optional[str] = Query(None, description="Kategoria materialu (INOX, MILD, ALU)"),
    grade: Optional[str] = Query(None, description="Gatunek materialu"),
    date_from: Optional[str] = Query(None, description="Data poczatkowa (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data koncowa (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pobierz dane historyczne cen do wykresu.

    Zwraca dane w formacie Chart.js:
    - labels: daty
    - datasets: serie danych (gatunek + powierzchnia)
    """
    from ..models.price import PriceChangeAudit

    # Parse dates
    try:
        from_date = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
        to_date = datetime.strptime(date_to, "%Y-%m-%d") if date_to else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Nieprawidlowy format daty")

    # Build query for audit history
    query = db.query(PriceChangeAudit)

    if from_date:
        query = query.filter(PriceChangeAudit.created_at >= from_date)
    if to_date:
        query = query.filter(PriceChangeAudit.created_at <= to_date)

    audits = query.order_by(PriceChangeAudit.created_at).limit(100).all()

    # If no data, return empty response
    if not audits:
        return {
            "labels": [],
            "datasets": [],
            "stats": {
                "totalChanges": 0,
                "avgPrice": 0,
                "trend": 0,
            }
        }

    # Group by date and aggregate
    from collections import defaultdict
    daily_data = defaultdict(lambda: {"changes": 0, "total_value": 0, "count": 0})

    for audit in audits:
        date_key = audit.created_at.strftime("%Y-%m-%d")
        daily_data[date_key]["changes"] += 1
        daily_data[date_key]["total_value"] += audit.new_total
        daily_data[date_key]["count"] += audit.affected_count

    # Build response
    labels = sorted(daily_data.keys())
    values = [daily_data[d]["total_value"] / max(daily_data[d]["count"], 1) for d in labels]

    # Calculate stats
    total_changes = sum(d["changes"] for d in daily_data.values())
    avg_price = sum(values) / len(values) if values else 0
    trend = ((values[-1] - values[0]) / values[0] * 100) if len(values) >= 2 and values[0] > 0 else 0

    return {
        "labels": [datetime.strptime(d, "%Y-%m-%d").strftime("%d.%m") for d in labels],
        "datasets": [
            {
                "label": "Srednia cena (PLN/kg)",
                "data": values,
            }
        ],
        "stats": {
            "totalChanges": total_changes,
            "avgPrice": round(avg_price, 2),
            "trend": round(trend, 1),
        }
    }
