"""Endpointy API dla cen."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.material import MaterialCategory
from ..models.price import Price, SourceType
from ..schemas.pricing import PriceCreate, PriceResponse

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/", response_model=list[PriceResponse])
async def list_prices(
    material_id: Optional[int] = Query(None, description="Filtruj po materiale"),
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    thickness: Optional[float] = Query(None, description="Filtruj po grubości"),
    source_type: Optional[SourceType] = Query(None, description="Filtruj po źródle"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Pobierz listę cen z opcjonalnymi filtrami."""
    query = db.query(Price)

    if material_id:
        query = query.filter(Price.material_id == material_id)

    if thickness:
        query = query.filter(Price.thickness == thickness)

    if source_type:
        query = query.filter(Price.source_type == source_type)

    # TODO: Filtrowanie po kategorii wymaga joina z materials

    return query.offset(offset).limit(limit).all()


@router.get("/{price_id}", response_model=PriceResponse)
async def get_price(price_id: int, db: Session = Depends(get_db)):
    """Pobierz szczegóły ceny."""
    price = db.query(Price).filter(Price.id == price_id).first()

    if not price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    return price


@router.post("/", response_model=PriceResponse, status_code=201)
async def create_price(data: PriceCreate, db: Session = Depends(get_db)):
    """Utwórz nową cenę."""
    price = Price(**data.model_dump())
    db.add(price)
    db.commit()
    db.refresh(price)

    return price


@router.put("/{price_id}", response_model=PriceResponse)
async def update_price(
    price_id: int, data: PriceCreate, db: Session = Depends(get_db)
):
    """Aktualizuj cenę."""
    price = db.query(Price).filter(Price.id == price_id).first()

    if not price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    for key, value in data.model_dump().items():
        setattr(price, key, value)

    db.commit()
    db.refresh(price)

    return price


@router.delete("/{price_id}", status_code=204)
async def delete_price(price_id: int, db: Session = Depends(get_db)):
    """Usuń cenę."""
    price = db.query(Price).filter(Price.id == price_id).first()

    if not price:
        raise HTTPException(status_code=404, detail="Cena nie znaleziona")

    db.delete(price)
    db.commit()
