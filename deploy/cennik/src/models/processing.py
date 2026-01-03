"""Modele obróbki wykańczającej - szlif i folia."""

from enum import Enum
from typing import Optional

from sqlalchemy import String, Float, Boolean, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class GrindingProvider(str, Enum):
    """Dostawcy usług szlifowania."""

    CAMU = "CAMU"
    BABCIA = "BABCIA"
    BORYS = "BORYS"
    COSTA = "COSTA"  # Nowa szlifiernia


class GrindingGrit(str, Enum):
    """Granulacje szlifu."""

    K80_K120 = "K80/K120"      # Gruby
    K240_K180 = "K240/K180"    # Średni
    K320_K400 = "K320/K400"    # Drobny


class GrindingPrice(Base):
    """Cennik szlifowania - ceny za kg wg grubości i granulacji.

    Zawiera dane z arkusza "DANE SZLIF".
    Cena = 0 oznacza kombinację zablokowaną (niedostępną).
    """

    __tablename__ = "grinding_prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Dostawca szlifu
    provider: Mapped[GrindingProvider] = mapped_column(SQLEnum(GrindingProvider), index=True)

    # Granulacja (dla CAMU, BABCIA, COSTA)
    grit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    # Wariant szerokości (dla BORYS: x1000/1250/1500 lub x2000)
    width_variant: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Grubość blachy
    thickness: Mapped[float] = mapped_column(Float, index=True)

    # Cena PLN/kg (0 = zablokowane)
    price_pln_per_kg: Mapped[float] = mapped_column(Float, default=0)

    # Czy z zabezpieczeniem SB (scotch-brite)?
    with_sb: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Unikalność kombinacji
    __table_args__ = (
        UniqueConstraint(
            'provider', 'grit', 'thickness', 'width_variant', 'with_sb',
            name='uq_grinding_price'
        ),
    )

    def is_available(self) -> bool:
        """Sprawdź czy kombinacja jest dostępna (cena > 0)."""
        return self.price_pln_per_kg > 0 and self.is_active

    def __repr__(self) -> str:
        status = "dostępne" if self.is_available() else "zablokowane"
        return (
            f"<GrindingPrice {self.provider.value} {self.grit or self.width_variant} "
            f"{self.thickness}mm @ {self.price_pln_per_kg} PLN/kg ({status})>"
        )


class FilmType(str, Enum):
    """Typy folii ochronnej."""

    FOLIA_ZWYKLA = "FOLIA_ZWYKLA"      # FZ - zwykła
    FOLIA_FIBER = "FOLIA_FIBER"         # FF - fiber
    NOVACEL_4228 = "Novacel 4228"
    NITTO_3100 = "Nitto 3100"
    NITTO_3067M = "Nitto 3067M"
    NITTO_AFP585 = "NITTO AFP585"
    NITTO_224PR = "NITTO 224PR"


class FilmPrice(Base):
    """Cennik folii ochronnej - ceny za kg wg grubości blachy.

    Zawiera dane z arkusza "DANE FOLIA".
    Cena zależna od grubości blachy (cieńsza blacha = więcej m² na kg).
    """

    __tablename__ = "film_prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Typ folii
    film_type: Mapped[FilmType] = mapped_column(SQLEnum(FilmType))

    # Grubość blachy
    thickness: Mapped[float] = mapped_column(Float, index=True)

    # Cena PLN/kg
    price_pln_per_kg: Mapped[float] = mapped_column(Float)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return (
            f"<FilmPrice {self.film_type.value} {self.thickness}mm "
            f"@ {self.price_pln_per_kg} PLN/kg>"
        )


class ProcessingOption(Base):
    """Konfiguracja obróbki dostępnej dla danego materiału.

    Określa jakie kombinacje szlif+folia są dostępne dla danego
    gatunku/powierzchni/grubości.
    """

    __tablename__ = "processing_options"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Klucz: gatunek + powierzchnia (lub NULL dla uniwersalnych)
    grade: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    surface_finish: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Zakres grubości
    thickness_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Zakres szerokości
    width_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Dozwolony szlif
    grinding_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    grinding_allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    # Dozwolona folia
    film_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    film_allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    # Uwagi (np. "NIE SZLIFUJEMY")
    notes: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<ProcessingOption {self.grade} {self.surface_finish}>"


# Mapowanie nazw z Excela na typy
EXCEL_FILM_MAPPING = {
    "cena FZ": FilmType.FOLIA_ZWYKLA,
    "cena FF": FilmType.FOLIA_FIBER,
    "FOLIA ZWYKŁA": FilmType.FOLIA_ZWYKLA,
    "FOLIA FIBER": FilmType.FOLIA_FIBER,
    "Novacel 4228": FilmType.NOVACEL_4228,
    "Nitto 3100": FilmType.NITTO_3100,
    "Nitto 3067M": FilmType.NITTO_3067M,
    "NITTO AFP585": FilmType.NITTO_AFP585,
    "NITTO 224PR": FilmType.NITTO_224PR,
}

EXCEL_GRINDING_MAPPING = {
    "szlif CAMU": GrindingProvider.CAMU,
    "szlif BABCIA": GrindingProvider.BABCIA,
    "szlif BORYS": GrindingProvider.BORYS,
    "szlif COSTA": GrindingProvider.COSTA,
}
