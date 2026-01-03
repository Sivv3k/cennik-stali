"""Endpointy API dla materiałów."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.material import Material, MaterialCategory
from ..schemas.pricing import MaterialCreate, MaterialResponse

router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.get("/", response_model=list[MaterialResponse])
async def list_materials(
    category: Optional[MaterialCategory] = Query(None, description="Filtruj po kategorii"),
    db: Session = Depends(get_db),
):
    """Pobierz listę wszystkich materiałów."""
    query = db.query(Material)

    if category:
        query = query.filter(Material.category == category)

    return query.all()


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: int, db: Session = Depends(get_db)):
    """Pobierz szczegóły materiału."""
    material = db.query(Material).filter(Material.id == material_id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Materiał nie znaleziony")

    return material


@router.post("/", response_model=MaterialResponse, status_code=201)
async def create_material(data: MaterialCreate, db: Session = Depends(get_db)):
    """Utwórz nowy materiał."""
    # Sprawdź czy już istnieje
    existing = db.query(Material).filter(Material.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Materiał o tej nazwie już istnieje")

    material = Material(**data.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)

    return material


@router.delete("/{material_id}", status_code=204)
async def delete_material(material_id: int, db: Session = Depends(get_db)):
    """Usuń materiał."""
    material = db.query(Material).filter(Material.id == material_id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Materiał nie znaleziony")

    db.delete(material)
    db.commit()
