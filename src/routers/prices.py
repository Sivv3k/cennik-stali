"""Endpointy API dla cen."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.material import MaterialCategory
from ..models.price import BasePrice
from ..schemas.pricing import BasePriceCreate, BasePriceResponse

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/", response_model=list[BasePriceResponse])
async def list_prices(
    material_id: Optional[int] = Query(None, description="Filtruj po materiale"),
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    thickness: Optional[float] = Query(None, description="Filtruj po grubości"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Pobierz liste cen z opcjonalnymi filtrami."""
    query = db.query(BasePrice).filter(BasePrice.is_active == True)

    if material_id:
        query = query.filter(BasePrice.material_id == material_id)

    if thickness:
        query = query.filter(BasePrice.thickness == thickness)

    # TODO: Filtrowanie po kategorii wymaga joina z materials

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
