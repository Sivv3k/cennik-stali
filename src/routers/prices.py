"""Endpointy API dla cen."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import distinct

from ..database import get_db
from ..models.material import Material, MaterialCategory
from ..models.price import BasePrice
from ..models.processing import GrindingPrice, FilmPrice, GrindingProvider, FilmType
from ..models.machine import (
    MachinePrice, MachineType, OperationType,
    get_available_machines, can_do_multiblanking,
    optimize_source_width, calculate_all_source_options,
    MACHINE_LIMITS, SOURCE_WIDTHS,
)
from ..schemas.pricing import BasePriceCreate, BasePriceResponse

router = APIRouter(prefix="/api/prices", tags=["prices"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/", response_class=HTMLResponse)
async def list_prices_html(
    request: Request,
    category: Optional[str] = Query(""),
    grade: Optional[str] = Query(""),
    surface: Optional[str] = Query(""),
    thickness: Optional[str] = Query(""),
    width: Optional[str] = Query(""),
    length: Optional[str] = Query(""),
    machine: Optional[str] = Query(""),
    operation: Optional[str] = Query(""),
    target_width: Optional[str] = Query(""),
    grinding_provider: Optional[str] = Query(""),
    grinding_grit: Optional[str] = Query(""),
    grinding_double: Optional[str] = Query(""),
    film_type: Optional[str] = Query(""),
    film_double: Optional[str] = Query(""),
    quantity: Optional[str] = Query("1"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Pobierz liste cen jako HTML (dla HTMX)."""
    # Konwertuj puste stringi na None/wartosci
    category = category if category else None
    grade = grade if grade else None
    surface = surface if surface else None
    machine = machine if machine else None
    operation = operation if operation else "CTL"
    grinding_provider = grinding_provider if grinding_provider else None
    grinding_grit = grinding_grit if grinding_grit else None
    film_type = film_type if film_type else None

    # Czy dwustronnie?
    is_grinding_double = grinding_double == "on"
    is_film_double = film_double == "on"

    thickness_val = float(thickness) if thickness else None
    width_val = float(width) if width else None
    length_val = float(length) if length else None
    target_width_val = float(target_width) if target_width else None
    quantity_val = int(quantity) if quantity else 1

    query = db.query(BasePrice).options(joinedload(BasePrice.material)).filter(BasePrice.is_active == True)

    # Filtrowanie po kategorii materialu
    if category:
        query = query.join(Material).filter(Material.category == category)

    # Filtrowanie po gatunku (obsluga AISI i EN)
    if grade:
        if not category:
            query = query.join(Material)
        query = query.filter(
            (Material.grade == grade) |
            (Material.grade.ilike(f"%{grade}%")) |
            (Material.name.ilike(f"%{grade}%"))
        )

    # Filtrowanie po grubosci
    if thickness_val:
        query = query.filter(BasePrice.thickness == thickness_val)

    # Filtrowanie po powierzchni
    if surface:
        query = query.filter(BasePrice.surface_finish == surface)

    # Filtrowanie po szerokosci zrodlowej
    if width_val:
        query = query.filter(BasePrice.width == width_val)

    prices = query.limit(limit).all()

    # Przygotuj dane dla szablonu
    price_rows = []
    density = 7.9  # kg/dm3

    for p in prices:
        base_price = p.price_pln_per_kg or 0
        current_thickness = p.thickness or thickness_val
        current_width = width_val or p.width
        current_length = length_val or p.length

        # Pobierz doplate za maszyne
        machine_cost = 0
        machine_label = None
        if machine and current_thickness:
            try:
                machine_enum = MachineType(machine)
                operation_enum = OperationType(operation)
                machine_price = db.query(MachinePrice).filter(
                    MachinePrice.machine_type == machine_enum,
                    MachinePrice.operation_type == operation_enum,
                    MachinePrice.thickness == current_thickness,
                    MachinePrice.is_active == True
                ).first()
                if machine_price:
                    machine_cost = machine_price.surcharge_pln_per_kg
                    machine_label = f"{machine} {operation}"
            except ValueError:
                pass

        # Pobierz cene szlifu z matrycy
        grinding_cost = 0
        grinding_label = None
        if grinding_provider and current_thickness:
            try:
                provider_enum = GrindingProvider(grinding_provider)
                grinding_query = db.query(GrindingPrice).filter(
                    GrindingPrice.is_active == True,
                    GrindingPrice.thickness == current_thickness,
                    GrindingPrice.provider == provider_enum
                )
                if grinding_grit:
                    grinding_query = grinding_query.filter(GrindingPrice.grit == grinding_grit)
                grinding_price_obj = grinding_query.first()
                if grinding_price_obj:
                    grinding_cost = grinding_price_obj.price_pln_per_kg
                    if is_grinding_double:
                        grinding_cost *= 2
                    grinding_label = f"Szlif {grinding_provider}"
                    if grinding_grit:
                        grinding_label += f" {grinding_grit}"
                    if is_grinding_double:
                        grinding_label += " 2x"
            except ValueError:
                pass

        # Pobierz cene folii z matrycy
        film_cost = 0
        film_label = None
        if film_type and current_thickness:
            try:
                film_enum = FilmType(film_type)
                film_price_obj = db.query(FilmPrice).filter(
                    FilmPrice.is_active == True,
                    FilmPrice.thickness == current_thickness,
                    FilmPrice.film_type == film_enum
                ).first()
                if film_price_obj:
                    film_cost = film_price_obj.price_pln_per_kg
                    if is_film_double:
                        film_cost *= 2
                    film_label = f"Folia {film_type.replace('_', ' ')}"
                    if is_film_double:
                        film_label += " 2x"
            except ValueError:
                pass

        total_price_kg = base_price + machine_cost + grinding_cost + film_cost

        # Oblicz cene za m2
        price_per_m2 = None
        if current_thickness and total_price_kg:
            price_per_m2 = total_price_kg * current_thickness * density / 1000

        # Oblicz cene arkusza/sztuki
        sheet_price = None
        pieces_per_sheet = 1
        optimization_info = None

        if current_width and current_length and current_thickness and total_price_kg:
            # Multiblanking - optymalizacja odpadu
            if operation == "MULTIBLANKING" and target_width_val:
                opt = optimize_source_width(target_width_val)
                if opt:
                    pieces_per_sheet = opt["pieces_per_sheet"]
                    optimization_info = {
                        "source_width": opt["source_width"],
                        "pieces": pieces_per_sheet,
                        "waste_mm": opt["waste_mm"],
                        "utilization": opt["utilization_pct"],
                    }
                    # Uzyj optymalnej szerokosci zrodlowej
                    current_width = opt["source_width"]

            # Waga arkusza zrodlowego
            weight_kg = (current_width / 1000) * (current_length / 1000) * current_thickness * density
            source_sheet_price = weight_kg * total_price_kg

            # Cena sztuki (dla multiblankingu dzielimy przez ilosc sztuk)
            sheet_price = source_sheet_price / pieces_per_sheet

        # Formatowanie wymiaru: grubosc x szerokosc x dlugosc
        dimension_str = None
        if current_thickness and current_width and current_length:
            dimension_str = f"{current_thickness} × {int(current_width)} × {int(current_length)}"

        # Formatowanie gatunku z powierzchnia: "1.4301 2B"
        grade_surface = f"{p.material.grade if p.material else '?'} {p.surface_finish}"

        price_rows.append({
            "grade_surface": grade_surface,
            "dimension": dimension_str,
            "thickness": current_thickness,
            "width": current_width,
            "length": current_length,
            "surface_type": p.surface_finish,
            # Etykiety obrobki
            "machine_label": machine_label,
            "grinding_label": grinding_label,
            "film_label": film_label,
            # Skladniki ceny
            "base_price_kg": base_price,
            "machine_cost": machine_cost,
            "grinding_cost": grinding_cost,
            "film_cost": film_cost,
            # Ceny
            "price_per_kg": total_price_kg if total_price_kg > 0 else None,
            "price_per_m2": price_per_m2,
            "sheet_price": sheet_price,
            "quantity": quantity_val,
            "total_price": sheet_price * quantity_val if sheet_price else None,
            # Optymalizacja multiblankingu
            "optimization": optimization_info,
            "pieces_per_sheet": pieces_per_sheet,
        })

    return templates.TemplateResponse(
        "price_table.html",
        {
            "request": request,
            "prices": price_rows,
            "has_machine": machine is not None,
            "has_grinding": grinding_provider is not None,
            "has_film": film_type is not None,
            "is_multiblanking": operation == "MULTIBLANKING",
        }
    )


@router.get("/json", response_model=list[BasePriceResponse])
async def list_prices_json(
    material_id: Optional[int] = Query(None, description="Filtruj po materiale"),
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    thickness: Optional[float] = Query(None, description="Filtruj po grubości"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Pobierz liste cen jako JSON."""
    query = db.query(BasePrice).filter(BasePrice.is_active == True)

    if material_id:
        query = query.filter(BasePrice.material_id == material_id)

    if thickness:
        query = query.filter(BasePrice.thickness == thickness)

    return query.offset(offset).limit(limit).all()


@router.get("/{price_id}", response_model=BasePriceResponse)
async def get_price(price_id: int, db: Session = Depends(get_db)):
    """Pobierz szczegoly ceny."""
    price = db.query(BasePrice).filter(BasePrice.id == price_id).first()

    if not price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    return price


@router.post("/", response_model=BasePriceResponse, status_code=201)
async def create_price(data: BasePriceCreate, db: Session = Depends(get_db)):
    """Utworz nowa cene."""
    price = BasePrice(**data.model_dump())
    db.add(price)
    db.commit()
    db.refresh(price)

    return price


@router.put("/{price_id}", response_model=BasePriceResponse)
async def update_price(
    price_id: int, data: BasePriceCreate, db: Session = Depends(get_db)
):
    """Aktualizuj cene."""
    price = db.query(BasePrice).filter(BasePrice.id == price_id).first()

    if not price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    for key, value in data.model_dump().items():
        setattr(price, key, value)

    db.commit()
    db.refresh(price)

    return price


@router.delete("/{price_id}", status_code=204)
async def delete_price(price_id: int, db: Session = Depends(get_db)):
    """Usun cene."""
    price = db.query(BasePrice).filter(BasePrice.id == price_id).first()

    if not price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    db.delete(price)
    db.commit()


@router.get("/grinding-options/")
async def get_grinding_options(db: Session = Depends(get_db)):
    """Pobierz dostepne opcje szlifu z matrycy."""
    # Pobierz unikalne kombinacje provider + grit
    options = db.query(
        GrindingPrice.provider,
        GrindingPrice.grit
    ).filter(
        GrindingPrice.is_active == True,
        GrindingPrice.price_pln_per_kg > 0
    ).distinct().all()

    # Grupuj po dostawcy
    result = {}
    for provider, grit in options:
        provider_name = provider.value if provider else "INNE"
        if provider_name not in result:
            result[provider_name] = []
        if grit and grit not in result[provider_name]:
            result[provider_name].append(grit)

    return result


@router.get("/film-options/")
async def get_film_options(db: Session = Depends(get_db)):
    """Pobierz dostepne opcje folii z matrycy."""
    # Pobierz unikalne typy folii
    options = db.query(
        distinct(FilmPrice.film_type)
    ).filter(
        FilmPrice.is_active == True,
        FilmPrice.price_pln_per_kg > 0
    ).all()

    return [opt[0].value if hasattr(opt[0], 'value') else str(opt[0]) for opt in options]


@router.get("/grinding-price/")
async def get_grinding_price(
    provider: str = Query(..., description="Dostawca szlifu"),
    grit: Optional[str] = Query(None, description="Granulacja"),
    thickness: float = Query(..., description="Grubosc blachy"),
    db: Session = Depends(get_db)
):
    """Pobierz cene szlifu z matrycy."""
    query = db.query(GrindingPrice).filter(
        GrindingPrice.is_active == True,
        GrindingPrice.thickness == thickness
    )

    # Dopasuj dostawce
    try:
        provider_enum = GrindingProvider(provider)
        query = query.filter(GrindingPrice.provider == provider_enum)
    except ValueError:
        return {"price_per_kg": 0, "error": "Nieznany dostawca"}

    if grit:
        query = query.filter(GrindingPrice.grit == grit)

    price = query.first()
    if price:
        return {"price_per_kg": price.price_pln_per_kg}
    return {"price_per_kg": 0}


@router.get("/film-price/")
async def get_film_price(
    film_type: str = Query(..., description="Typ folii"),
    thickness: float = Query(..., description="Grubosc blachy"),
    db: Session = Depends(get_db)
):
    """Pobierz cene folii z matrycy."""
    query = db.query(FilmPrice).filter(
        FilmPrice.is_active == True,
        FilmPrice.thickness == thickness
    )

    # Dopasuj typ folii
    try:
        film_enum = FilmType(film_type)
        query = query.filter(FilmPrice.film_type == film_enum)
    except ValueError:
        return {"price_per_kg": 0, "error": "Nieznany typ folii"}

    price = query.first()
    if price:
        return {"price_per_kg": price.price_pln_per_kg}
    return {"price_per_kg": 0}


@router.get("/filter-options/")
async def get_filter_options(
    category: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    surface: Optional[str] = Query(None),
    thickness: Optional[float] = Query(None),
    width: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    """Pobierz dostepne opcje filtrow na podstawie aktualnego wyboru."""
    base_query = db.query(BasePrice).options(
        joinedload(BasePrice.material)
    ).filter(BasePrice.is_active == True)

    # Aplikuj istniejace filtry
    if category:
        base_query = base_query.join(Material).filter(Material.category == category)

    if grade:
        if not category:
            base_query = base_query.join(Material)
        base_query = base_query.filter(
            (Material.grade == grade) |
            (Material.grade.ilike(f"%{grade}%")) |
            (Material.name.ilike(f"%{grade}%"))
        )

    if surface:
        base_query = base_query.filter(BasePrice.surface_finish == surface)

    if thickness:
        base_query = base_query.filter(BasePrice.thickness == thickness)

    if width:
        base_query = base_query.filter(BasePrice.width == width)

    # Pobierz unikalne wartosci dla kazdego pola
    all_prices = base_query.all()

    # Zbierz unikalne wartosci
    grades = set()
    surfaces = set()
    thicknesses = set()
    widths = set()

    for p in all_prices:
        if p.material:
            grades.add(p.material.grade)
        surfaces.add(p.surface_finish)
        thicknesses.add(p.thickness)
        widths.add(p.width)

    # Okresl dostepne maszyny na podstawie grubosci i szerokosci
    max_thickness = max(thicknesses) if thicknesses else 0
    max_width = max(widths) if widths else 0

    if thickness:
        max_thickness = thickness
    if width:
        max_width = width

    available_machines = get_available_machines(max_thickness, max_width)
    multiblanking_available = can_do_multiblanking(max_thickness, max_width)

    return {
        "grades": sorted(list(grades)),
        "surfaces": sorted(list(surfaces)),
        "thicknesses": sorted(list(thicknesses)),
        "widths": sorted(list(widths)),
        "machines": [m.value for m in available_machines],
        "multiblanking_available": multiblanking_available,
        "source_widths": SOURCE_WIDTHS,
    }


@router.get("/machine-options/")
async def get_machine_options(
    thickness: float = Query(..., description="Grubosc materialu"),
    width: float = Query(..., description="Szerokosc materialu"),
):
    """Pobierz dostepne maszyny dla podanych parametrow."""
    available = get_available_machines(thickness, width)
    multiblanking = can_do_multiblanking(thickness, width)

    return {
        "machines": [
            {
                "type": m.value,
                "max_thickness": MACHINE_LIMITS[m]["max_thickness"],
                "max_width": MACHINE_LIMITS[m]["max_width"],
                "operations": [op.value for op in MACHINE_LIMITS[m]["operations"]],
            }
            for m in available
        ],
        "multiblanking_available": multiblanking,
    }


@router.get("/machine-price/")
async def get_machine_price(
    machine: str = Query(..., description="Typ maszyny (ATH/RBI)"),
    operation: str = Query(..., description="Typ operacji (CTL/MULTIBLANKING)"),
    thickness: float = Query(..., description="Grubosc materialu"),
    db: Session = Depends(get_db)
):
    """Pobierz doplate za maszyne."""
    try:
        machine_enum = MachineType(machine)
        operation_enum = OperationType(operation)
    except ValueError:
        return {"surcharge_per_kg": 0, "error": "Nieznany typ maszyny lub operacji"}

    price = db.query(MachinePrice).filter(
        MachinePrice.machine_type == machine_enum,
        MachinePrice.operation_type == operation_enum,
        MachinePrice.thickness == thickness,
        MachinePrice.is_active == True
    ).first()

    if price:
        return {"surcharge_per_kg": price.surcharge_pln_per_kg}

    # Jesli brak dokladnego dopasowania, szukaj najblizszej grubosci
    closest = db.query(MachinePrice).filter(
        MachinePrice.machine_type == machine_enum,
        MachinePrice.operation_type == operation_enum,
        MachinePrice.is_active == True
    ).order_by(
        (MachinePrice.thickness - thickness).abs()
    ).first()

    if closest:
        return {"surcharge_per_kg": closest.surcharge_pln_per_kg, "interpolated": True}

    return {"surcharge_per_kg": 0}


@router.get("/multiblanking-options/")
async def get_multiblanking_options(
    target_width: float = Query(..., description="Docelowa szerokosc arkusza"),
):
    """Oblicz opcje multiblankingu dla podanej szerokosci."""
    options = calculate_all_source_options(target_width)
    optimal = optimize_source_width(target_width)

    return {
        "target_width": target_width,
        "options": options,
        "optimal": optimal,
    }
