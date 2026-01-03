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
from ..schemas.pricing import BasePriceCreate, BasePriceResponse

router = APIRouter(prefix="/api/prices", tags=["prices"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/", response_class=HTMLResponse)
async def list_prices_html(
    request: Request,
    category: Optional[str] = Query(""),
    grade: Optional[str] = Query(""),
    source_type: Optional[str] = Query(""),
    thickness: Optional[str] = Query(""),
    surface: Optional[str] = Query(""),
    width: Optional[str] = Query(""),
    length: Optional[str] = Query(""),
    grinding_provider: Optional[str] = Query(""),
    grinding_grit: Optional[str] = Query(""),
    grinding_double: Optional[str] = Query(""),
    film_type: Optional[str] = Query(""),
    film_double: Optional[str] = Query(""),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Pobierz liste cen jako HTML (dla HTMX)."""
    # Konwertuj puste stringi na None/wartosci
    category = category if category else None
    grade = grade if grade else None
    source_type = source_type if source_type else None
    surface = surface if surface else None
    grinding_provider = grinding_provider if grinding_provider else None
    grinding_grit = grinding_grit if grinding_grit else None
    film_type = film_type if film_type else None

    # Czy dwustronnie?
    is_grinding_double = grinding_double == "on"
    is_film_double = film_double == "on"

    thickness_val = float(thickness) if thickness else None
    width_val = float(width) if width else None
    length_val = float(length) if length else None

    query = db.query(BasePrice).options(joinedload(BasePrice.material)).filter(BasePrice.is_active == True)

    # Filtrowanie po kategorii materialu
    if category:
        query = query.join(Material).filter(Material.category == category)

    # Filtrowanie po gatunku
    if grade:
        if not category:
            query = query.join(Material)
        query = query.filter(Material.grade == grade)

    # Filtrowanie po grubosci
    if thickness_val:
        query = query.filter(BasePrice.thickness == thickness_val)

    # Filtrowanie po powierzchni
    if surface:
        query = query.filter(BasePrice.surface_finish == surface)

    # Filtrowanie po szerokosci
    if width_val:
        query = query.filter(BasePrice.width == width_val)

    prices = query.limit(limit).all()

    # Przygotuj dane dla szablonu
    price_rows = []
    for p in prices:
        base_price = p.price_pln_per_kg or 0
        current_thickness = p.thickness or thickness_val

        # Pobierz cene szlifu z matrycy
        grinding_cost = 0
        grinding_label = None
        if grinding_provider and current_thickness:
            grinding_query = db.query(GrindingPrice).filter(
                GrindingPrice.is_active == True,
                GrindingPrice.thickness == current_thickness
            )
            try:
                provider_enum = GrindingProvider(grinding_provider)
                grinding_query = grinding_query.filter(GrindingPrice.provider == provider_enum)
                if grinding_grit:
                    grinding_query = grinding_query.filter(GrindingPrice.grit == grinding_grit)
                grinding_price_obj = grinding_query.first()
                if grinding_price_obj:
                    grinding_cost = grinding_price_obj.price_pln_per_kg
                    if is_grinding_double:
                        grinding_cost *= 2
                    grinding_label = f"{grinding_provider}"
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
            film_query = db.query(FilmPrice).filter(
                FilmPrice.is_active == True,
                FilmPrice.thickness == current_thickness
            )
            try:
                film_enum = FilmType(film_type)
                film_query = film_query.filter(FilmPrice.film_type == film_enum)
                film_price_obj = film_query.first()
                if film_price_obj:
                    film_cost = film_price_obj.price_pln_per_kg
                    if is_film_double:
                        film_cost *= 2
                    film_label = film_type.replace("_", " ")
                    if is_film_double:
                        film_label += " 2x"
            except ValueError:
                pass

        total_price_kg = base_price + grinding_cost + film_cost

        # Oblicz cene za m2 (gestosc stali ~7.9 g/cm3)
        density = 7.9  # kg/dm3
        price_per_m2 = None
        sheet_price = None

        if current_thickness and total_price_kg:
            price_per_m2 = total_price_kg * current_thickness * density / 1000

        # Oblicz cene arkusza: (szer/1000 x dl/1000 x grub x gestosc x cena/kg)
        if width_val and length_val and current_thickness and total_price_kg:
            area_m2 = (width_val / 1000) * (length_val / 1000)
            weight_kg = area_m2 * current_thickness * density
            sheet_price = weight_kg * total_price_kg

        price_rows.append({
            "material_name": p.material.name if p.material else "?",
            "grade": p.material.grade if p.material else "?",
            "thickness": current_thickness,
            "width": width_val or p.width,
            "length": length_val or p.length,
            "surface_type": p.surface_finish,
            "source_type": source_type or "arkusz",
            "grinding": grinding_label,
            "film": film_label,
            "base_price_kg": base_price,
            "grinding_cost": grinding_cost,
            "film_cost": film_cost,
            "price_per_kg": total_price_kg if total_price_kg > 0 else None,
            "price_per_m2": price_per_m2,
            "sheet_price": sheet_price,
        })

    return templates.TemplateResponse(
        "price_table.html",
        {
            "request": request,
            "prices": price_rows,
            "has_grinding": grinding_provider is not None,
            "has_film": film_type is not None,
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
