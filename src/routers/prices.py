"""Endpointy API dla cen."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.material import Material, MaterialCategory
from ..models.price import BasePrice
from ..schemas.pricing import BasePriceCreate, BasePriceResponse

router = APIRouter(prefix="/api/prices", tags=["prices"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/", response_class=HTMLResponse)
async def list_prices_html(
    request: Request,
    category: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    thickness: Optional[float] = Query(None),
    surface: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Pobierz liste cen jako HTML (dla HTMX)."""
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
    if thickness:
        query = query.filter(BasePrice.thickness == thickness)

    # Filtrowanie po powierzchni
    if surface:
        query = query.filter(BasePrice.surface_finish == surface)

    prices = query.limit(limit).all()

    # Przygotuj dane dla szablonu
    price_rows = []
    for p in prices:
        price_rows.append({
            "material_name": p.material.name if p.material else "?",
            "grade": p.material.grade if p.material else "?",
            "thickness": p.thickness,
            "surface_type": p.surface_finish,
            "finish": p.surface_finish,
            "source_type": source_type or "arkusz",
            "protective_film": False,
            "price_per_kg": p.price_pln_per_kg,
            "price_per_m2": p.price_pln_per_kg * p.thickness * 7.9 / 1000 if p.price_pln_per_kg else None,
        })

    return templates.TemplateResponse(
        "price_table.html",
        {"request": request, "prices": price_rows}
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
