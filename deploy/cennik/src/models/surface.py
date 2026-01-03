"""Modele powierzchni i wykończenia."""

from enum import Enum
from typing import Optional

from sqlalchemy import String, Float, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SurfaceType(str, Enum):
    """Typy powierzchni."""

    # Stal nierdzewna
    SURFACE_2B = "2B"           # Zimnowalcowana, wytrawiowana
    SURFACE_BA = "BA"           # Jasna wyżarzona
    SURFACE_NO1 = "No.1"        # Gorącowalcowana
    SURFACE_NO4 = "No.4"        # Szczotkowana
    SURFACE_MIRROR = "mirror"   # Lustrzana
    SURFACE_HAIRLINE = "HL"     # Szlif liniowy

    # Stal czarna
    SURFACE_HR = "HR"           # Gorącowalcowana (hot rolled)
    SURFACE_CR = "CR"           # Zimnowalcowana (cold rolled)
    SURFACE_PICKLED = "pickled" # Trawiona
    SURFACE_OILED = "oiled"     # Naoliwiona

    # Aluminium
    SURFACE_MILL = "mill"       # Mill finish
    SURFACE_ANODIZED = "anodized"  # Anodowana


class Finish(str, Enum):
    """Rodzaj obróbki wykańczającej."""

    NONE = "brak"
    BRUSHED = "szczotkowane"     # Szlifowanie szczotkami
    POLISHED = "polerowane"      # Polerowanie
    SATIN = "satynowe"           # Satynowanie
    GROUND = "szlifowane"        # Szlifowanie (różne granulacje)


class Surface(Base):
    """Model konfiguracji powierzchni."""

    __tablename__ = "surfaces"

    id: Mapped[int] = mapped_column(primary_key=True)

    surface_type: Mapped[SurfaceType] = mapped_column(SQLEnum(SurfaceType))
    finish: Mapped[Finish] = mapped_column(SQLEnum(Finish), default=Finish.NONE)

    # Szczegóły szlifowania
    grit: Mapped[Optional[int]] = mapped_column(nullable=True)  # Granulacja (np. 120, 240, 320)

    # Zabezpieczenie
    protective_film: Mapped[bool] = mapped_column(default=False)
    film_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Dodatkowy koszt za obróbkę (PLN/m² lub %)
    processing_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    processing_cost_type: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True
    )  # "PLN" lub "%"

    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<Surface {self.surface_type.value} / {self.finish.value}>"
