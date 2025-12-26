"""Serwis do obsługi logiki cennikowej."""

from typing import Optional

from sqlalchemy.orm import Session

from ..models.material import Material, MaterialCategory
from ..models.price import Price, SourceType
from ..models.surface import Surface


class PricingService:
    """Serwis do kalkulacji i zarządzania cenami."""

    def __init__(self, db: Session):
        self.db = db

    def get_price_table(
        self,
        category: Optional[MaterialCategory] = None,
        source_type: Optional[SourceType] = None,
        thickness_min: Optional[float] = None,
        thickness_max: Optional[float] = None,
    ) -> list[dict]:
        """Pobierz tabelę cennikową z filtrami."""
        query = (
            self.db.query(Price, Material, Surface)
            .join(Material, Price.material_id == Material.id)
            .outerjoin(Surface, Price.surface_id == Surface.id)
        )

        if category:
            query = query.filter(Material.category == category)

        if source_type:
            query = query.filter(Price.source_type == source_type)

        if thickness_min:
            query = query.filter(Price.thickness >= thickness_min)

        if thickness_max:
            query = query.filter(Price.thickness <= thickness_max)

        results = []
        for price, material, surface in query.all():
            results.append({
                "material_name": material.name,
                "material_category": material.category,
                "grade": material.grade,
                "thickness": price.thickness,
                "width": price.width,
                "length": price.length,
                "source_type": price.source_type,
                "surface_type": surface.surface_type if surface else None,
                "finish": surface.finish if surface else None,
                "protective_film": surface.protective_film if surface else False,
                "price_per_kg": price.price_per_kg,
                "price_per_m2": price.price_per_m2,
                "currency": price.currency,
            })

        return results

    def calculate_price(
        self,
        material_id: int,
        thickness: float,
        width: float,
        length: float,
        source_type: SourceType,
        surface_id: Optional[int] = None,
    ) -> dict:
        """Oblicz cenę dla zadanych parametrów."""
        # Znajdź bazową cenę
        price = (
            self.db.query(Price)
            .filter(
                Price.material_id == material_id,
                Price.thickness == thickness,
                Price.source_type == source_type,
            )
            .first()
        )

        if not price:
            return {"error": "Nie znaleziono ceny dla podanych parametrów"}

        # Pobierz materiał dla gęstości
        material = self.db.query(Material).filter(Material.id == material_id).first()

        # Oblicz powierzchnię w m²
        area_m2 = (width / 1000) * (length / 1000)

        # Oblicz wagę (jeśli znana gęstość)
        weight_kg = None
        if material and material.density:
            # gęstość w g/cm³, grubość w mm, wymiary w mm
            volume_cm3 = (thickness / 10) * (width / 10) * (length / 10)
            weight_kg = (material.density * volume_cm3) / 1000

        result = {
            "area_m2": round(area_m2, 4),
            "weight_kg": round(weight_kg, 3) if weight_kg else None,
        }

        # Oblicz cenę
        if price.price_per_m2:
            result["price_by_area"] = round(price.price_per_m2 * area_m2, 2)

        if price.price_per_kg and weight_kg:
            result["price_by_weight"] = round(price.price_per_kg * weight_kg, 2)

        # Dodaj koszt obróbki powierzchni
        if surface_id:
            surface = self.db.query(Surface).filter(Surface.id == surface_id).first()
            if surface and surface.processing_cost:
                if surface.processing_cost_type == "PLN":
                    result["surface_cost"] = surface.processing_cost * area_m2
                elif surface.processing_cost_type == "%":
                    base_price = result.get("price_by_weight") or result.get("price_by_area", 0)
                    result["surface_cost"] = base_price * (surface.processing_cost / 100)

        result["currency"] = price.currency

        return result
