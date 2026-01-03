"""Serwis do kalkulacji cen z uwzględnieniem wszystkich modyfikatorów."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from ..models import (
    Material,
    MaterialCategory,
    BasePrice,
    ThicknessModifier,
    WidthModifier,
    ExchangeRate,
    GrindingPrice,
    GrindingProvider,
    FilmPrice,
    FilmType,
    ProcessingOption,
)


@dataclass
class PriceBreakdown:
    """Szczegółowy rozbicie ceny."""

    # Ceny składowe (PLN/kg)
    base_price: float
    film_cost: float = 0.0
    grinding_cost: float = 0.0

    # Cena końcowa
    total_price_pln_per_kg: float = 0.0
    total_price_eur_per_kg: float = 0.0

    # Kurs waluty
    exchange_rate: float = 4.38

    # Wymiary i waga
    thickness: float = 0.0
    width: float = 0.0
    length: float = 0.0
    weight_kg: float = 0.0
    area_m2: float = 0.0

    # Opis konfiguracji
    material_grade: str = ""
    surface_finish: str = ""
    film_type: Optional[str] = None
    grinding_provider: Optional[str] = None
    grinding_grit: Optional[str] = None

    # Uwagi
    notes: Optional[str] = None

    def calculate_totals(self):
        """Oblicz sumy."""
        self.total_price_pln_per_kg = (
            self.base_price + self.film_cost + self.grinding_cost
        )
        if self.exchange_rate > 0:
            self.total_price_eur_per_kg = (
                self.total_price_pln_per_kg / self.exchange_rate
            )

    def to_dict(self) -> dict:
        """Konwersja do słownika."""
        return {
            "base_price_pln_kg": round(self.base_price, 4),
            "film_cost_pln_kg": round(self.film_cost, 4),
            "grinding_cost_pln_kg": round(self.grinding_cost, 4),
            "total_price_pln_kg": round(self.total_price_pln_per_kg, 4),
            "total_price_eur_kg": round(self.total_price_eur_per_kg, 4),
            "exchange_rate": self.exchange_rate,
            "dimensions": {
                "thickness_mm": self.thickness,
                "width_mm": self.width,
                "length_mm": self.length,
            },
            "weight_kg": round(self.weight_kg, 3),
            "area_m2": round(self.area_m2, 4),
            "configuration": {
                "material": self.material_grade,
                "surface": self.surface_finish,
                "film": self.film_type,
                "grinding": self.grinding_provider,
                "grit": self.grinding_grit,
            },
            "notes": self.notes,
        }


class PricingService:
    """Serwis do kalkulacji i zarządzania cenami."""

    # Gęstość stali nierdzewnej w g/cm³
    STEEL_DENSITY = 7.9

    def __init__(self, db: Session):
        self.db = db
        self._exchange_rate: Optional[float] = None

    @property
    def exchange_rate(self) -> float:
        """Pobierz aktualny kurs EUR/PLN."""
        if self._exchange_rate is None:
            rate = (
                self.db.query(ExchangeRate)
                .filter(ExchangeRate.is_active == True)
                .order_by(ExchangeRate.valid_from.desc())
                .first()
            )
            self._exchange_rate = rate.rate if rate else 4.38
        return self._exchange_rate

    def calculate_weight(
        self, thickness: float, width: float, length: float, density: float = None
    ) -> float:
        """Oblicz wagę arkusza w kg.

        Args:
            thickness: grubość w mm
            width: szerokość w mm
            length: długość w mm
            density: gęstość w g/cm³ (domyślnie stal nierdzewna)

        Returns:
            Waga w kg
        """
        if density is None:
            density = self.STEEL_DENSITY

        # Objętość w cm³
        volume_cm3 = (thickness / 10) * (width / 10) * (length / 10)
        # Waga w kg
        return (density * volume_cm3) / 1000

    def calculate_area(self, width: float, length: float) -> float:
        """Oblicz powierzchnię arkusza w m²."""
        return (width / 1000) * (length / 1000)

    def get_base_price(
        self,
        material_id: int,
        surface_finish: str,
        thickness: float,
        width: float,
    ) -> Optional[BasePrice]:
        """Pobierz cenę bazową dla zadanych parametrów."""
        return (
            self.db.query(BasePrice)
            .filter(
                BasePrice.material_id == material_id,
                BasePrice.surface_finish == surface_finish,
                BasePrice.thickness == thickness,
                BasePrice.width == width,
                BasePrice.is_active == True,
            )
            .order_by(BasePrice.valid_from.desc())
            .first()
        )

    def get_film_price(
        self, film_type: FilmType, thickness: float
    ) -> Optional[float]:
        """Pobierz cenę folii dla danej grubości."""
        film = (
            self.db.query(FilmPrice)
            .filter(
                FilmPrice.film_type == film_type,
                FilmPrice.thickness == thickness,
                FilmPrice.is_active == True,
            )
            .first()
        )
        return film.price_pln_per_kg if film else None

    def get_grinding_price(
        self,
        provider: GrindingProvider,
        thickness: float,
        grit: Optional[str] = None,
        width_variant: Optional[str] = None,
        with_sb: bool = False,
    ) -> Optional[float]:
        """Pobierz cenę szlifowania."""
        query = self.db.query(GrindingPrice).filter(
            GrindingPrice.provider == provider,
            GrindingPrice.thickness == thickness,
            GrindingPrice.is_active == True,
        )

        if grit:
            query = query.filter(GrindingPrice.grit == grit)
        if width_variant:
            query = query.filter(GrindingPrice.width_variant == width_variant)
        if with_sb:
            query = query.filter(GrindingPrice.with_sb == True)

        result = query.first()
        return result.price_pln_per_kg if result else None

    def check_processing_allowed(
        self,
        grade: str,
        surface_finish: str,
        thickness: float,
        width: float,
        grinding_provider: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """Sprawdź czy obróbka jest dozwolona dla danej konfiguracji.

        Returns:
            (czy_dozwolone, uwagi)
        """
        option = (
            self.db.query(ProcessingOption)
            .filter(
                ProcessingOption.grade == grade,
                ProcessingOption.surface_finish == surface_finish,
            )
            .first()
        )

        if not option:
            return True, None  # Brak ograniczeń

        # Sprawdź zakres grubości
        if option.thickness_min and thickness < option.thickness_min:
            return False, f"Grubość poniżej minimum ({option.thickness_min}mm)"
        if option.thickness_max and thickness > option.thickness_max:
            return False, f"Grubość powyżej maksimum ({option.thickness_max}mm)"

        # Sprawdź zakres szerokości
        if option.width_min and width < option.width_min:
            return False, f"Szerokość poniżej minimum ({option.width_min}mm)"
        if option.width_max and width > option.width_max:
            return False, f"Szerokość powyżej maksimum ({option.width_max}mm)"

        # Sprawdź szlifowanie
        if grinding_provider and not option.grinding_allowed:
            return False, option.notes or "Szlifowanie niedostępne"

        return True, option.notes

    def calculate_price(
        self,
        material_id: int,
        surface_finish: str,
        thickness: float,
        width: float,
        length: float,
        film_type: Optional[FilmType] = None,
        grinding_provider: Optional[GrindingProvider] = None,
        grinding_grit: Optional[str] = None,
        grinding_width_variant: Optional[str] = None,
        with_sb: bool = False,
    ) -> PriceBreakdown:
        """Oblicz pełną cenę z wszystkimi modyfikatorami.

        Args:
            material_id: ID materiału
            surface_finish: wykończenie powierzchni (2B, BA, 1D, etc.)
            thickness: grubość w mm
            width: szerokość w mm
            length: długość w mm
            film_type: typ folii ochronnej
            grinding_provider: dostawca szlifu
            grinding_grit: granulacja szlifu
            grinding_width_variant: wariant szerokości dla BORYS
            with_sb: czy z zabezpieczeniem SB

        Returns:
            PriceBreakdown z rozbiciem ceny
        """
        # Pobierz materiał
        material = self.db.query(Material).filter(Material.id == material_id).first()
        if not material:
            raise ValueError(f"Nie znaleziono materiału o ID {material_id}")

        # Inicjalizuj wynik
        breakdown = PriceBreakdown(
            base_price=0.0,
            thickness=thickness,
            width=width,
            length=length,
            material_grade=material.grade,
            surface_finish=surface_finish,
            exchange_rate=self.exchange_rate,
        )

        # Oblicz wymiary
        breakdown.weight_kg = self.calculate_weight(
            thickness, width, length, material.density
        )
        breakdown.area_m2 = self.calculate_area(width, length)

        # Pobierz cenę bazową
        base_price = self.get_base_price(material_id, surface_finish, thickness, width)
        if not base_price:
            raise ValueError(
                f"Nie znaleziono ceny bazowej dla: {material.grade} {surface_finish} "
                f"{thickness}mm x {width}mm"
            )

        breakdown.base_price = base_price.price_pln_per_kg
        breakdown.notes = base_price.notes

        # Sprawdź czy obróbka dozwolona
        if grinding_provider:
            allowed, notes = self.check_processing_allowed(
                material.grade, surface_finish, thickness, width,
                grinding_provider.value if isinstance(grinding_provider, GrindingProvider) else grinding_provider
            )
            if not allowed:
                breakdown.notes = notes
                breakdown.calculate_totals()
                return breakdown

        # Dodaj koszt folii
        if film_type:
            film_cost = self.get_film_price(film_type, thickness)
            if film_cost:
                breakdown.film_cost = film_cost
                breakdown.film_type = film_type.value

        # Dodaj koszt szlifowania
        if grinding_provider:
            grind_cost = self.get_grinding_price(
                grinding_provider, thickness, grinding_grit,
                grinding_width_variant, with_sb
            )
            if grind_cost:
                breakdown.grinding_cost = grind_cost
                breakdown.grinding_provider = grinding_provider.value
                breakdown.grinding_grit = grinding_grit

        # Oblicz sumy
        breakdown.calculate_totals()

        return breakdown

    def get_price_table(
        self,
        category: Optional[MaterialCategory] = None,
        grade: Optional[str] = None,
        surface_finish: Optional[str] = None,
        thickness_min: Optional[float] = None,
        thickness_max: Optional[float] = None,
        width: Optional[float] = None,
    ) -> list[dict]:
        """Pobierz tabelę cennikową z filtrami."""
        query = (
            self.db.query(BasePrice, Material)
            .join(Material, BasePrice.material_id == Material.id)
            .filter(BasePrice.is_active == True)
        )

        if category:
            query = query.filter(Material.category == category)
        if grade:
            query = query.filter(Material.grade == grade)
        if surface_finish:
            query = query.filter(BasePrice.surface_finish == surface_finish)
        if thickness_min:
            query = query.filter(BasePrice.thickness >= thickness_min)
        if thickness_max:
            query = query.filter(BasePrice.thickness <= thickness_max)
        if width:
            query = query.filter(BasePrice.width == width)

        results = []
        for price, material in query.all():
            results.append({
                "id": price.id,
                "material_id": material.id,
                "material_name": material.name,
                "grade": material.grade,
                "category": material.category.value,
                "surface_finish": price.surface_finish,
                "thickness": price.thickness,
                "width": price.width,
                "length": price.length,
                "price_pln_per_kg": price.price_pln_per_kg,
                "price_eur_per_kg": round(
                    price.price_pln_per_kg / self.exchange_rate, 4
                ),
                "notes": price.notes,
            })

        return results

    def get_available_options(
        self, material_id: int, surface_finish: str, thickness: float
    ) -> dict:
        """Pobierz dostępne opcje obróbki dla danej konfiguracji."""
        material = self.db.query(Material).filter(Material.id == material_id).first()
        if not material:
            return {"error": "Material not found"}

        # Sprawdź ograniczenia
        allowed, notes = self.check_processing_allowed(
            material.grade, surface_finish, thickness, 1000
        )

        # Pobierz dostępne folie
        films = (
            self.db.query(FilmPrice)
            .filter(
                FilmPrice.thickness == thickness,
                FilmPrice.is_active == True,
            )
            .all()
        )

        # Pobierz dostępne szlify
        grindings = (
            self.db.query(GrindingPrice)
            .filter(
                GrindingPrice.thickness == thickness,
                GrindingPrice.is_active == True,
            )
            .all()
        )

        return {
            "processing_allowed": allowed,
            "notes": notes,
            "films": [
                {
                    "type": f.film_type.value,
                    "price_pln_kg": f.price_pln_per_kg,
                }
                for f in films
            ],
            "grindings": [
                {
                    "provider": g.provider.value,
                    "grit": g.grit,
                    "width_variant": g.width_variant,
                    "with_sb": g.with_sb,
                    "price_pln_kg": g.price_pln_per_kg,
                }
                for g in grindings
            ],
        }
