"""Serwis walidacji szlifowania - sprawdza dostępność na podstawie matryc cen."""

from typing import Optional

from sqlalchemy.orm import Session

from ..models import GrindingPrice, GrindingProvider


class GrindingValidationService:
    """Serwis do walidacji dostępności szlifowania.

    Kluczowa zasada: cena > 0 = dostępne, cena = 0 = zablokowane.
    Wszystkie ograniczenia są definiowane przez matryce cen, nie przez kod.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_available_providers(
        self,
        thickness: float,
        width: float,
        grit: Optional[str] = None,
    ) -> list[dict]:
        """Zwróć dostępne opcje szlifu dla parametrów.

        Sprawdza matryce cen - dostępne są te gdzie price > 0.

        Args:
            thickness: grubość blachy w mm
            width: szerokość blachy w mm
            grit: opcjonalna granulacja do filtrowania

        Returns:
            Lista słowników z dostępnymi dostawcami i ich opcjami
        """
        results = []

        for provider in GrindingProvider:
            query = self.db.query(GrindingPrice).filter(
                GrindingPrice.provider == provider,
                GrindingPrice.thickness == thickness,
                GrindingPrice.price_pln_per_kg > 0,  # Tylko dostępne (cena > 0)
                GrindingPrice.is_active == True,
            )

            if grit:
                query = query.filter(GrindingPrice.grit == grit)

            # Dla BORYS sprawdź wariant szerokości
            if provider == GrindingProvider.BORYS:
                if width <= 1500:
                    query = query.filter(
                        GrindingPrice.width_variant == "x1000/1250/1500"
                    )
                else:
                    query = query.filter(GrindingPrice.width_variant == "x2000")

            prices = query.all()

            if prices:
                # Grupuj po granulacji i wariancie SB
                grits_set = set()
                prices_dict = {}

                for p in prices:
                    key = f"{p.grit}{'_sb' if p.with_sb else ''}"
                    grits_set.add(p.grit)
                    prices_dict[key] = p.price_pln_per_kg

                results.append({
                    "provider": provider.value,
                    "grits": list(grits_set),
                    "prices": prices_dict,
                    "width_variant": prices[0].width_variant if prices else None,
                })

        return results

    def is_grinding_available(
        self,
        provider: GrindingProvider,
        thickness: float,
        width: float,
        grit: str,
        with_sb: bool = False,
    ) -> tuple[bool, Optional[float]]:
        """Sprawdź czy konkretna konfiguracja szlifu jest dostępna.

        Args:
            provider: dostawca szlifu
            thickness: grubość blachy w mm
            width: szerokość blachy w mm
            grit: granulacja (np. "K320/K400")
            with_sb: czy z zabezpieczeniem SB

        Returns:
            Krotka (is_available, price_if_available)
        """
        query = self.db.query(GrindingPrice).filter(
            GrindingPrice.provider == provider,
            GrindingPrice.thickness == thickness,
            GrindingPrice.grit == grit,
            GrindingPrice.with_sb == with_sb,
            GrindingPrice.is_active == True,
        )

        # Dla BORYS sprawdź wariant szerokości
        if provider == GrindingProvider.BORYS:
            if width <= 1500:
                query = query.filter(
                    GrindingPrice.width_variant == "x1000/1250/1500"
                )
            else:
                query = query.filter(GrindingPrice.width_variant == "x2000")

        price = query.first()

        if price and price.price_pln_per_kg > 0:
            return True, price.price_pln_per_kg
        return False, None

    def get_grinding_matrix(
        self,
        provider: GrindingProvider,
        width_variant: Optional[str] = None,
    ) -> dict:
        """Pobierz pełną matrycę cen szlifu dla dostawcy.

        Zwraca wszystkie grubości - te z ceną 0 są zablokowane.

        Args:
            provider: dostawca szlifu
            width_variant: wariant szerokości (dla BORYS)

        Returns:
            Słownik z matrycą cen
        """
        query = self.db.query(GrindingPrice).filter(
            GrindingPrice.provider == provider,
            GrindingPrice.is_active == True,
        )

        if width_variant:
            query = query.filter(GrindingPrice.width_variant == width_variant)

        prices = query.order_by(GrindingPrice.thickness).all()

        # Grupuj po grubości
        matrix = {}
        thicknesses = set()
        grits = set()

        for p in prices:
            thicknesses.add(p.thickness)
            if p.thickness not in matrix:
                matrix[p.thickness] = {}

            key = f"{p.grit}{'_sb' if p.with_sb else ''}"
            grits.add(key)

            matrix[p.thickness][key] = {
                "id": p.id,
                "price": p.price_pln_per_kg,
                "is_blocked": p.price_pln_per_kg == 0,
                "grit": p.grit,
                "with_sb": p.with_sb,
            }

        return {
            "provider": provider.value,
            "width_variant": width_variant,
            "matrix": matrix,
            "thicknesses": sorted(thicknesses),
            "grits": sorted(grits),
        }

    def update_grinding_price(
        self,
        provider: GrindingProvider,
        thickness: float,
        grit: str,
        price: float,
        width_variant: Optional[str] = None,
        with_sb: bool = False,
    ) -> GrindingPrice:
        """Aktualizuj lub utwórz cenę szlifu.

        Wpisanie price=0 blokuje kombinację.

        Args:
            provider: dostawca szlifu
            thickness: grubość blachy
            grit: granulacja
            price: cena PLN/kg (0 = zablokowany)
            width_variant: wariant szerokości (dla BORYS)
            with_sb: czy z zabezpieczeniem SB

        Returns:
            Zaktualizowany lub utworzony obiekt GrindingPrice
        """
        existing = self.db.query(GrindingPrice).filter(
            GrindingPrice.provider == provider,
            GrindingPrice.thickness == thickness,
            GrindingPrice.grit == grit,
            GrindingPrice.width_variant == width_variant,
            GrindingPrice.with_sb == with_sb,
        ).first()

        if existing:
            existing.price_pln_per_kg = price
            self.db.commit()
            return existing
        else:
            new_price = GrindingPrice(
                provider=provider,
                thickness=thickness,
                grit=grit,
                price_pln_per_kg=price,
                width_variant=width_variant,
                with_sb=with_sb,
            )
            self.db.add(new_price)
            self.db.commit()
            return new_price

    def bulk_update_matrix(
        self,
        provider: GrindingProvider,
        updates: list[dict],
    ) -> int:
        """Masowa aktualizacja matrycy cen.

        Args:
            provider: dostawca szlifu
            updates: lista słowników z aktualizacjami
                     [{thickness, grit, price, width_variant?, with_sb?}, ...]

        Returns:
            Liczba zaktualizowanych wpisów
        """
        count = 0
        for update in updates:
            self.update_grinding_price(
                provider=provider,
                thickness=update["thickness"],
                grit=update["grit"],
                price=update["price"],
                width_variant=update.get("width_variant"),
                with_sb=update.get("with_sb", False),
            )
            count += 1

        return count
