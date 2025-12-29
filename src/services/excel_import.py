"""Serwis do importu danych z plików Excel - rozbudowany parser."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd
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
    EXCEL_FILM_MAPPING,
    EXCEL_GRINDING_MAPPING,
)


@dataclass
class ImportResult:
    """Wynik importu."""

    success: bool = True
    sheets_processed: int = 0
    materials_imported: int = 0
    base_prices_imported: int = 0
    grinding_prices_imported: int = 0
    film_prices_imported: int = 0
    modifiers_imported: int = 0
    errors: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "sheets_processed": self.sheets_processed,
            "materials_imported": self.materials_imported,
            "base_prices_imported": self.base_prices_imported,
            "grinding_prices_imported": self.grinding_prices_imported,
            "film_prices_imported": self.film_prices_imported,
            "modifiers_imported": self.modifiers_imported,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ExcelImporter:
    """Importer danych z plików Excel - obsługuje format cennika."""

    # Mapowanie gatunków na materiały
    GRADE_MAPPING = {
        "1.4301": ("Stal nierdzewna 304", MaterialCategory.STAINLESS_STEEL, 7.9),
        "1.4404": ("Stal nierdzewna 316L", MaterialCategory.STAINLESS_STEEL, 8.0),
        "1.4016": ("Stal nierdzewna 430", MaterialCategory.STAINLESS_STEEL, 7.7),
    }

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.result = ImportResult()

    def preview_file(self, file_path: Path) -> dict[str, Any]:
        """Podgląd struktury pliku Excel."""
        xl = pd.ExcelFile(file_path)

        preview = {
            "filename": file_path.name,
            "sheets": [],
        }

        for sheet_name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet_name, nrows=10, header=None)
            preview["sheets"].append({
                "name": sheet_name,
                "columns_count": df.shape[1],
                "rows_count": len(pd.read_excel(xl, sheet_name=sheet_name, header=None)),
                "preview": df.head(10).fillna("").to_dict(orient="records"),
            })

        return preview

    def import_file(self, file_path: Path) -> ImportResult:
        """Importuj dane z pliku Excel.

        Obsługuje strukturę:
        - 'cennik baza' - główny cennik z cenami bazowymi
        - 'DANE DO WPROWADZENIA' - modyfikatory cen
        - 'DANE SZLIF' - cennik szlifowania
        - 'DANE FOLIA' - cennik folii
        """
        if not self.db:
            raise ValueError("Brak połączenia z bazą danych")

        xl = pd.ExcelFile(file_path)
        self.result = ImportResult()

        # Przetwarzaj arkusze w odpowiedniej kolejności
        sheet_handlers = {
            "cennik baza": self._import_base_prices,
            "DANE DO WPROWADZENIA": self._import_modifiers,
            "DANE SZLIF": self._import_grinding_prices,
            "DANE FOLIA": self._import_film_prices,
        }

        for sheet_name, handler in sheet_handlers.items():
            if sheet_name in xl.sheet_names:
                try:
                    df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
                    handler(df, sheet_name)
                    self.result.sheets_processed += 1
                except Exception as e:
                    self.result.errors.append({
                        "sheet": sheet_name,
                        "error": str(e),
                    })
                    self.result.success = False

        self.db.commit()
        return self.result

    def _get_or_create_material(self, grade: str) -> Material:
        """Pobierz lub stwórz materiał na podstawie gatunku."""
        material = self.db.query(Material).filter(Material.grade == grade).first()

        if not material:
            if grade in self.GRADE_MAPPING:
                name, category, density = self.GRADE_MAPPING[grade]
            else:
                name = f"Materiał {grade}"
                category = MaterialCategory.STAINLESS_STEEL
                density = 7.9

            material = Material(
                name=name,
                grade=grade,
                category=category,
                density=density,
            )
            self.db.add(material)
            self.db.flush()
            self.result.materials_imported += 1

        return material

    def _import_base_prices(self, df: pd.DataFrame, sheet_name: str):
        """Import cen bazowych z arkusza 'cennik baza'.

        Kolumny:
        ID, Gatunek, powierzchnia, grubość, szerokość, długość,
        z papierem, cena FZ, cena FF,
        szlif BABCIA + FZ, szlif BABCIA + FF,
        szlif CAMU + FZ, szlif CAMU + FF,
        szlif BORYS + FZ, szlif BORYS + FF
        """
        # Pierwszy wiersz to nagłówki
        headers = [str(h).strip() for h in df.iloc[0].tolist()]
        df = df.iloc[1:].copy()
        df.columns = headers

        for idx, row in df.iterrows():
            try:
                grade = str(row.get("Gatunek", "")).strip()
                if not grade or grade == "nan":
                    continue

                material = self._get_or_create_material(grade)

                surface = str(row.get("powierzchnia", "")).strip()
                thickness = float(row.get("grubość", 0))
                width = float(row.get("szerokość", 0))
                length = float(row.get("długość", 0))

                # Cena bazowa "z papierem"
                base_price_value = row.get("z papierem")
                if pd.notna(base_price_value):
                    # Sprawdź czy pozycja już istnieje
                    existing = self.db.query(BasePrice).filter(
                        BasePrice.material_id == material.id,
                        BasePrice.surface_finish == surface,
                        BasePrice.thickness == thickness,
                        BasePrice.width == width,
                    ).first()

                    if existing:
                        existing.price_pln_per_kg = float(base_price_value)
                    else:
                        bp = BasePrice(
                            material_id=material.id,
                            surface_finish=surface,
                            thickness=thickness,
                            width=width,
                            length=length,
                            price_pln_per_kg=float(base_price_value),
                        )
                        self.db.add(bp)
                        self.result.base_prices_imported += 1

            except Exception as e:
                self.result.warnings.append(
                    f"Wiersz {idx}: {str(e)}"
                )

    def _import_modifiers(self, df: pd.DataFrame, sheet_name: str):
        """Import modyfikatorów cen z arkusza 'DANE DO WPROWADZENIA'.

        Zawiera:
        - Ceny bazowe dla gatunków i powierzchni
        - Dodatki za szerokość
        - Dodatki za grubość dla różnych kombinacji
        - Kurs EUR
        """
        # Ten arkusz ma złożoną strukturę - dane w różnych sekcjach
        # Parsuj kurs EUR
        for idx, row in df.iterrows():
            for col_idx, val in enumerate(row):
                if str(val).strip() == "KURS EURO":
                    # Kurs w następnej kolumnie
                    rate_val = row.iloc[col_idx + 1]
                    if pd.notna(rate_val):
                        rate = ExchangeRate(
                            currency_from="EUR",
                            currency_to="PLN",
                            rate=float(rate_val),
                        )
                        self.db.add(rate)
                        break

        self.result.modifiers_imported += 1

    def _import_grinding_prices(self, df: pd.DataFrame, sheet_name: str):
        """Import cennika szlifowania z arkusza 'DANE SZLIF'.

        Struktura:
        - CAMU: K320/K400, K320/K400+SB, SB, K240/K180, 240/180+SB, K80/K120
        - BABCIA: te same kolumny
        - BORYS: x1000/1250/1500, x2000
        """
        current_provider = None
        grit_columns = {}

        for idx, row in df.iterrows():
            first_val = str(row.iloc[0]).strip()

            # Wykryj sekcję dostawcy
            if first_val in ["CAMU", "BABCIA", "COSTA"]:
                current_provider = GrindingProvider(first_val)
                continue

            # Nagłówki kolumn z granulacjami
            if first_val == "" or first_val == "nan":
                # Sprawdź czy to wiersz nagłówkowy
                if any("K320" in str(v) or "K240" in str(v) for v in row if pd.notna(v)):
                    grit_columns = {}
                    for col_idx, val in enumerate(row):
                        val_str = str(val).strip()
                        if val_str and val_str != "nan":
                            grit_columns[col_idx] = val_str
                continue

            # Parsuj BORYS osobno (inna struktura)
            if "BORYS" in first_val:
                # BORYS ma inną strukturę - parsuj z osobnych kolumn
                continue

            # Parsuj ceny dla grubości
            if current_provider and first_val.replace(".", "").isdigit():
                thickness = float(first_val)

                for col_idx, grit_name in grit_columns.items():
                    price_val = row.iloc[col_idx]
                    if pd.notna(price_val) and str(price_val).replace(".", "").isdigit():
                        with_sb = "+SB" in grit_name or grit_name == "SB [zł/kg]"
                        grit = None
                        if "K320" in grit_name or "K400" in grit_name:
                            grit = "K320/K400"
                        elif "K240" in grit_name or "K180" in grit_name:
                            grit = "K240/K180"
                        elif "K80" in grit_name or "K120" in grit_name:
                            grit = "K80/K120"

                        gp = GrindingPrice(
                            provider=current_provider,
                            grit=grit,
                            thickness=thickness,
                            price_pln_per_kg=float(price_val),
                            with_sb=with_sb,
                        )
                        self.db.add(gp)
                        self.result.grinding_prices_imported += 1

        # Parsuj BORYS (osobne kolumny po prawej stronie)
        for idx, row in df.iterrows():
            # Szukaj kolumny BORYS
            for col_idx, val in enumerate(row):
                if "BORYS" in str(val):
                    # Parsuj dane BORYS
                    # Struktura: grubość | cena x1000/1250/1500 | cena x2000
                    pass

    def _import_film_prices(self, df: pd.DataFrame, sheet_name: str):
        """Import cennika folii z arkusza 'DANE FOLIA'.

        Kolumny: grubość, Novacel 4228, FOLIA FIBER, FOLIA ZWYKŁA,
                 Nitto 3100, Nitto 3067M, NITTO AFP585, NITTO 224PR
        """
        # Znajdź wiersz nagłówkowy
        header_row = None
        for idx, row in df.iterrows():
            if any("Novacel" in str(v) or "FOLIA" in str(v) or "Nitto" in str(v)
                   for v in row if pd.notna(v)):
                header_row = idx
                break

        if header_row is None:
            self.result.warnings.append("Nie znaleziono nagłówków folii")
            return

        # Pobierz nagłówki
        headers = {}
        for col_idx, val in enumerate(df.iloc[header_row]):
            val_str = str(val).strip()
            if val_str in EXCEL_FILM_MAPPING:
                headers[col_idx] = EXCEL_FILM_MAPPING[val_str]

        # Parsuj ceny
        for idx in range(header_row + 1, len(df)):
            row = df.iloc[idx]
            thickness_val = row.iloc[0]

            if pd.isna(thickness_val):
                continue

            try:
                thickness = float(thickness_val)
            except (ValueError, TypeError):
                continue

            for col_idx, film_type in headers.items():
                price_val = row.iloc[col_idx]
                if pd.notna(price_val):
                    try:
                        fp = FilmPrice(
                            film_type=film_type,
                            thickness=thickness,
                            price_pln_per_kg=float(price_val),
                        )
                        self.db.add(fp)
                        self.result.film_prices_imported += 1
                    except (ValueError, TypeError):
                        pass

    def import_materials_from_config(self, config: list[dict]) -> int:
        """Import materiałów z konfiguracji.

        Przykład config:
        [
            {
                "grade": "1.4301",
                "name": "Stal nierdzewna 304",
                "category": "stal_nierdzewna",
                "density": 7.9,
                "equivalent_grades": "AISI 304, X5CrNi18-10"
            },
            ...
        ]
        """
        if not self.db:
            raise ValueError("Brak połączenia z bazą danych")

        count = 0
        for item in config:
            existing = self.db.query(Material).filter(
                Material.grade == item["grade"]
            ).first()

            if not existing:
                material = Material(
                    name=item["name"],
                    grade=item["grade"],
                    category=MaterialCategory(item["category"]),
                    density=item.get("density", 7.9),
                    equivalent_grades=item.get("equivalent_grades"),
                    description=item.get("description"),
                )
                self.db.add(material)
                count += 1

        self.db.commit()
        return count


# Predefiniowane konfiguracje materiałów
STAINLESS_STEEL_GRADES = [
    {
        "grade": "1.4301",
        "name": "Stal nierdzewna 304",
        "category": "stal_nierdzewna",
        "density": 7.9,
        "equivalent_grades": "AISI 304, X5CrNi18-10",
        "description": "Austenityczna stal nierdzewna, uniwersalna, odporna na korozję",
    },
    {
        "grade": "1.4404",
        "name": "Stal nierdzewna 316L",
        "category": "stal_nierdzewna",
        "density": 8.0,
        "equivalent_grades": "AISI 316L, X2CrNiMo17-12-2",
        "description": "Austenityczna stal nierdzewna z molibdenem, lepsza odporność na korozję",
    },
    {
        "grade": "1.4016",
        "name": "Stal nierdzewna 430",
        "category": "stal_nierdzewna",
        "density": 7.7,
        "equivalent_grades": "AISI 430, X6Cr17",
        "description": "Ferrytyczna stal nierdzewna, magnetyczna, ekonomiczna",
    },
]

CARBON_STEEL_GRADES = [
    {
        "grade": "DC01",
        "name": "Stal czarna DC01",
        "category": "stal_czarna",
        "density": 7.85,
        "equivalent_grades": "1.0330, St12",
        "description": "Stal zimnowalcowana do tłoczenia",
    },
    {
        "grade": "S235JR",
        "name": "Stal konstrukcyjna S235JR",
        "category": "stal_czarna",
        "density": 7.85,
        "equivalent_grades": "1.0038, St37-2",
        "description": "Stal konstrukcyjna ogólnego przeznaczenia",
    },
    {
        "grade": "S355JR",
        "name": "Stal konstrukcyjna S355JR",
        "category": "stal_czarna",
        "density": 7.85,
        "equivalent_grades": "1.0045, St52-3",
        "description": "Stal konstrukcyjna o podwyższonej wytrzymałości",
    },
]

ALUMINUM_GRADES = [
    {
        "grade": "1050",
        "name": "Aluminium 1050",
        "category": "aluminium",
        "density": 2.71,
        "equivalent_grades": "Al 99.5",
        "description": "Aluminium czyste techniczne",
    },
    {
        "grade": "5754",
        "name": "Aluminium 5754",
        "category": "aluminium",
        "density": 2.66,
        "equivalent_grades": "AlMg3",
        "description": "Stop Al-Mg, dobra odporność na korozję",
    },
    {
        "grade": "6061",
        "name": "Aluminium 6061",
        "category": "aluminium",
        "density": 2.70,
        "equivalent_grades": "AlMg1SiCu",
        "description": "Stop Al-Mg-Si, wszechstronny, utwardzalny",
    },
]

ALL_MATERIAL_GRADES = STAINLESS_STEEL_GRADES + CARBON_STEEL_GRADES + ALUMINUM_GRADES
