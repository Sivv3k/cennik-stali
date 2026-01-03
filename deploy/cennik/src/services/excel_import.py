"""Serwis do importu danych z plików Excel - rozbudowany parser."""

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

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


@dataclass
class ImportDiffItem:
    """Pojedyncza zmiana w imporcie."""

    row_number: int
    change_type: str  # added, updated, removed, unchanged, error
    data_type: str  # base_price, grinding, film

    # Identyfikatory
    grade: Optional[str] = None
    surface_finish: Optional[str] = None
    thickness: Optional[float] = None
    width: Optional[float] = None
    provider: Optional[str] = None
    film_type: Optional[str] = None
    grit: Optional[str] = None

    # Wartosci
    current_price: Optional[float] = None
    new_price: Optional[float] = None
    price_change: Optional[float] = None

    # Bledy
    error_message: Optional[str] = None


@dataclass
class ImportAnalysis:
    """Wynik analizy pliku przed importem."""

    import_id: str
    filename: str
    total_rows: int = 0
    valid_rows: int = 0
    error_rows: int = 0

    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0

    items: list[ImportDiffItem] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Dane tymczasowe do zastosowania
    pending_changes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "import_id": self.import_id,
            "filename": self.filename,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "error_rows": self.error_rows,
            "added": self.added,
            "updated": self.updated,
            "removed": self.removed,
            "unchanged": self.unchanged,
            "items": [
                {
                    "row_number": item.row_number,
                    "change_type": item.change_type,
                    "data_type": item.data_type,
                    "grade": item.grade,
                    "surface_finish": item.surface_finish,
                    "thickness": item.thickness,
                    "width": item.width,
                    "provider": item.provider,
                    "film_type": item.film_type,
                    "grit": item.grit,
                    "current_price": item.current_price,
                    "new_price": item.new_price,
                    "price_change": item.price_change,
                    "error_message": item.error_message,
                }
                for item in self.items
            ],
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

    def analyze_file(self, file_path: Path) -> ImportAnalysis:
        """Analizuj plik Excel i wygeneruj podglad zmian bez importowania.

        Args:
            file_path: Sciezka do pliku Excel

        Returns:
            ImportAnalysis: Analiza z podgladem zmian
        """
        if not self.db:
            raise ValueError("Brak polaczenia z baza danych")

        import_id = str(uuid.uuid4())
        analysis = ImportAnalysis(
            import_id=import_id,
            filename=file_path.name,
        )

        xl = pd.ExcelFile(file_path)
        sheet_names_lower = {name.lower(): name for name in xl.sheet_names}

        # Znajdz arkusz cen bazowych (elastyczne dopasowanie)
        base_sheet = None
        for pattern in ["cennik baza", "ceny bazowe", "base prices", "base"]:
            if pattern in sheet_names_lower:
                base_sheet = sheet_names_lower[pattern]
                break
        # Sprawdz tez pierwszy arkusz jesli ma kolumne "Gatunek"
        if not base_sheet and xl.sheet_names:
            first_df = pd.read_excel(xl, sheet_name=xl.sheet_names[0], header=None, nrows=5)
            first_row = [str(v).lower() for v in first_df.iloc[0].tolist() if pd.notna(v)]
            if any("gatunek" in col for col in first_row):
                base_sheet = xl.sheet_names[0]

        if base_sheet:
            df = pd.read_excel(xl, sheet_name=base_sheet, header=None)
            self._analyze_base_prices(df, analysis)
        else:
            analysis.warnings.append(f"Nie znaleziono arkusza cen bazowych. Dostepne: {xl.sheet_names}")

        # Znajdz arkusz szlifu
        grinding_sheet = None
        for pattern in ["dane szlif", "cennik szlifu", "szlif", "grinding"]:
            if pattern in sheet_names_lower:
                grinding_sheet = sheet_names_lower[pattern]
                break

        if grinding_sheet:
            df = pd.read_excel(xl, sheet_name=grinding_sheet, header=None)
            self._analyze_grinding_prices(df, analysis)

        # Znajdz arkusz folii
        film_sheet = None
        for pattern in ["dane folia", "cennik folii", "folia", "film"]:
            if pattern in sheet_names_lower:
                film_sheet = sheet_names_lower[pattern]
                break

        if film_sheet:
            df = pd.read_excel(xl, sheet_name=film_sheet, header=None)
            self._analyze_film_prices(df, analysis)

        # Oblicz podsumowanie
        analysis.valid_rows = analysis.added + analysis.updated + analysis.unchanged
        analysis.error_rows = len([i for i in analysis.items if i.change_type == "error"])
        analysis.total_rows = analysis.valid_rows + analysis.error_rows

        # Jesli nic nie znaleziono, dodaj info o dostepnych arkuszach
        if analysis.total_rows == 0:
            analysis.warnings.append(f"Nie znaleziono danych do importu. Arkusze w pliku: {xl.sheet_names}")

        return analysis

    def _analyze_base_prices(self, df: pd.DataFrame, analysis: ImportAnalysis):
        """Analizuj ceny bazowe i wygeneruj diff."""
        # Pierwszy wiersz to naglowki
        raw_headers = [str(h).strip() for h in df.iloc[0].tolist()]
        df = df.iloc[1:].copy()
        df.columns = raw_headers

        # Mapuj naglowki elastycznie
        headers_lower = {h.lower(): h for h in raw_headers}

        def find_col(patterns):
            for p in patterns:
                if p in headers_lower:
                    return headers_lower[p]
            return None

        grade_col = find_col(["gatunek", "grade", "material"])
        surface_col = find_col(["powierzchnia", "surface", "wykończenie", "wykoncznie", "finish", "wykonczenie"])
        thickness_col = find_col(["grubość", "grubosc", "grubosc (mm)", "thickness"])
        width_col = find_col(["szerokość", "szerokosc", "szerokosc (mm)", "width"])
        price_col = find_col(["z papierem", "cena pln/kg", "cena", "price", "pln/kg"])

        if not grade_col:
            analysis.warnings.append(f"Nie znaleziono kolumny 'Gatunek'. Dostepne: {raw_headers[:10]}")
            return

        # Pre-load wszystkich materialow i cen do pamieci (optymalizacja)
        materials_map = {m.grade: m for m in self.db.query(Material).all()}

        # Mapa cen: (material_id, surface, thickness, width) -> BasePrice
        prices_map = {}
        for bp in self.db.query(BasePrice).all():
            key = (bp.material_id, bp.surface_finish, bp.thickness, bp.width)
            prices_map[key] = bp

        for idx, row in df.iterrows():
            row_number = idx + 1
            try:
                grade = str(row.get(grade_col, "")).strip() if grade_col else ""
                if not grade or grade == "nan":
                    continue

                surface = str(row.get(surface_col, "")).strip() if surface_col else ""
                thickness = float(row.get(thickness_col, 0)) if thickness_col else 0
                width = float(row.get(width_col, 0)) if width_col else 0
                new_price = row.get(price_col) if price_col else None

                if pd.isna(new_price):
                    continue

                new_price = float(new_price)

                # Znajdz material w pamieci
                material = materials_map.get(grade)

                if not material:
                    # Material nie istnieje - nowa pozycja
                    analysis.items.append(ImportDiffItem(
                        row_number=row_number,
                        change_type="added",
                        data_type="base_price",
                        grade=grade,
                        surface_finish=surface,
                        thickness=thickness,
                        width=width,
                        new_price=new_price,
                    ))
                    analysis.added += 1
                    analysis.pending_changes.append({
                        "type": "base_price",
                        "action": "add",
                        "grade": grade,
                        "surface_finish": surface,
                        "thickness": thickness,
                        "width": width,
                        "price": new_price,
                    })
                    continue

                # Sprawdz istniejaca cene w pamieci
                key = (material.id, surface, thickness, width)
                existing = prices_map.get(key)

                if existing:
                    current_price = existing.price_pln_per_kg
                    if abs(current_price - new_price) < 0.001:
                        # Bez zmian
                        analysis.items.append(ImportDiffItem(
                            row_number=row_number,
                            change_type="unchanged",
                            data_type="base_price",
                            grade=grade,
                            surface_finish=surface,
                            thickness=thickness,
                            width=width,
                            current_price=current_price,
                            new_price=new_price,
                        ))
                        analysis.unchanged += 1
                    else:
                        # Zmiana ceny
                        analysis.items.append(ImportDiffItem(
                            row_number=row_number,
                            change_type="updated",
                            data_type="base_price",
                            grade=grade,
                            surface_finish=surface,
                            thickness=thickness,
                            width=width,
                            current_price=current_price,
                            new_price=new_price,
                            price_change=new_price - current_price,
                        ))
                        analysis.updated += 1
                        analysis.pending_changes.append({
                            "type": "base_price",
                            "action": "update",
                            "id": existing.id,
                            "price": new_price,
                        })
                else:
                    # Nowa pozycja dla istniejacego materialu
                    analysis.items.append(ImportDiffItem(
                        row_number=row_number,
                        change_type="added",
                        data_type="base_price",
                        grade=grade,
                        surface_finish=surface,
                        thickness=thickness,
                        width=width,
                        new_price=new_price,
                    ))
                    analysis.added += 1
                    analysis.pending_changes.append({
                        "type": "base_price",
                        "action": "add",
                        "material_id": material.id,
                        "surface_finish": surface,
                        "thickness": thickness,
                        "width": width,
                        "price": new_price,
                    })

            except Exception as e:
                analysis.items.append(ImportDiffItem(
                    row_number=row_number,
                    change_type="error",
                    data_type="base_price",
                    error_message=str(e),
                ))
                analysis.errors.append({
                    "row": row_number,
                    "error": str(e),
                })

    def _analyze_grinding_prices(self, df: pd.DataFrame, analysis: ImportAnalysis):
        """Analizuj ceny szlifu i wygeneruj diff."""
        # Sprawdz czy to format eksportu (tabela z naglowkami) czy oryginalny format
        first_row = [str(v).lower() for v in df.iloc[0].tolist() if pd.notna(v)]

        if any("dostawca" in col for col in first_row):
            # Format eksportu - tabela z kolumnami
            self._analyze_grinding_export_format(df, analysis)
        else:
            # Oryginalny format DANE SZLIF
            self._analyze_grinding_original_format(df, analysis)

    def _analyze_grinding_export_format(self, df: pd.DataFrame, analysis: ImportAnalysis):
        """Analizuj cennik szlifu w formacie eksportu."""
        raw_headers = [str(h).strip() for h in df.iloc[0].tolist()]
        df = df.iloc[1:].copy()
        df.columns = raw_headers

        headers_lower = {h.lower(): h for h in raw_headers}

        def find_col(patterns):
            for p in patterns:
                if p in headers_lower:
                    return headers_lower[p]
            return None

        provider_col = find_col(["dostawca", "provider"])
        grit_col = find_col(["granulacja", "grit"])
        thickness_col = find_col(["grubosc (mm)", "grubosc", "thickness"])
        price_col = find_col(["cena pln/kg", "cena", "price"])
        sb_col = find_col(["z sb", "with_sb", "sb"])

        if not provider_col:
            analysis.warnings.append(f"Szlif: nie znaleziono kolumny 'Dostawca'. Dostepne: {raw_headers[:8]}")
            return

        # Pre-load cen szlifu do pamieci
        grinding_map = {}
        for gp in self.db.query(GrindingPrice).all():
            # Klucz zawiera width_variant dla poprawnego mapowania BORYS
            key = (gp.provider.value, gp.thickness, gp.grit, gp.with_sb, gp.width_variant)
            grinding_map[key] = gp

        # Znajdz kolumne width_variant
        width_var_col = find_col(["wariant szerokosci", "width_variant", "wariant"])

        for idx, row in df.iterrows():
            row_number = idx + 1
            try:
                provider_str = str(row.get(provider_col, "")).strip()
                if not provider_str or provider_str == "nan":
                    continue

                try:
                    provider = GrindingProvider(provider_str)
                except ValueError:
                    continue

                grit = str(row.get(grit_col, "")).strip() if grit_col else None
                if grit == "nan" or grit == "None":
                    grit = None
                thickness = float(row.get(thickness_col, 0)) if thickness_col else 0
                new_price = row.get(price_col) if price_col else None
                with_sb_val = str(row.get(sb_col, "")).strip().lower() if sb_col else ""
                with_sb = with_sb_val in ["tak", "yes", "true", "1"]
                width_variant = str(row.get(width_var_col, "")).strip() if width_var_col else None
                if width_variant == "nan" or width_variant == "":
                    width_variant = None

                if pd.isna(new_price):
                    continue
                new_price = float(new_price)

                # Sprawdz istniejaca cene w pamieci (z width_variant)
                key = (provider.value, thickness, grit, with_sb, width_variant)
                existing = grinding_map.get(key)

                if existing:
                    current_price = existing.price_pln_per_kg
                    if abs(current_price - new_price) < 0.001:
                        analysis.unchanged += 1
                    else:
                        analysis.items.append(ImportDiffItem(
                            row_number=row_number,
                            change_type="updated",
                            data_type="grinding",
                            provider=provider.value,
                            thickness=thickness,
                            grit=grit,
                            current_price=current_price,
                            new_price=new_price,
                            price_change=new_price - current_price,
                        ))
                        analysis.updated += 1
                        analysis.pending_changes.append({
                            "type": "grinding",
                            "action": "update",
                            "id": existing.id,
                            "price": new_price,
                        })
                else:
                    analysis.items.append(ImportDiffItem(
                        row_number=row_number,
                        change_type="added",
                        data_type="grinding",
                        provider=provider.value,
                        thickness=thickness,
                        grit=grit,
                        new_price=new_price,
                    ))
                    analysis.added += 1
                    analysis.pending_changes.append({
                        "type": "grinding",
                        "action": "add",
                        "provider": provider.value,
                        "thickness": thickness,
                        "grit": grit,
                        "with_sb": with_sb,
                        "width_variant": width_variant,
                        "price": new_price,
                    })
            except Exception as e:
                analysis.errors.append({"row": row_number, "error": str(e)})

    def _analyze_grinding_original_format(self, df: pd.DataFrame, analysis: ImportAnalysis):
        """Analizuj cennik szlifu w oryginalnym formacie DANE SZLIF."""
        current_provider = None
        grit_columns = {}
        row_number = 0

        for idx, row in df.iterrows():
            row_number = idx + 1
            first_val = str(row.iloc[0]).strip()

            # Wykryj sekcje dostawcy
            if first_val in ["CAMU", "BABCIA", "COSTA"]:
                try:
                    current_provider = GrindingProvider(first_val)
                except ValueError:
                    pass
                continue

            # Naglowki kolumn z granulacjami
            if first_val == "" or first_val == "nan":
                if any("K320" in str(v) or "K240" in str(v) for v in row if pd.notna(v)):
                    grit_columns = {}
                    for col_idx, val in enumerate(row):
                        val_str = str(val).strip()
                        if val_str and val_str != "nan":
                            grit_columns[col_idx] = val_str
                continue

            # Parsuj ceny dla grubosci
            if current_provider and first_val.replace(".", "").isdigit():
                thickness = float(first_val)

                for col_idx, grit_name in grit_columns.items():
                    price_val = row.iloc[col_idx]
                    if pd.notna(price_val) and str(price_val).replace(".", "").isdigit():
                        new_price = float(price_val)
                        with_sb = "+SB" in grit_name or grit_name == "SB [zł/kg]"

                        grit = None
                        if "K320" in grit_name or "K400" in grit_name:
                            grit = "K320/K400"
                        elif "K240" in grit_name or "K180" in grit_name:
                            grit = "K240/K180"
                        elif "K80" in grit_name or "K120" in grit_name:
                            grit = "K80/K120"

                        # Sprawdz istniejaca cene
                        existing = self.db.query(GrindingPrice).filter(
                            GrindingPrice.provider == current_provider,
                            GrindingPrice.thickness == thickness,
                            GrindingPrice.grit == grit,
                            GrindingPrice.with_sb == with_sb,
                        ).first()

                        if existing:
                            current_price = existing.price_pln_per_kg
                            if abs(current_price - new_price) < 0.001:
                                analysis.unchanged += 1
                            else:
                                analysis.items.append(ImportDiffItem(
                                    row_number=row_number,
                                    change_type="updated",
                                    data_type="grinding",
                                    provider=current_provider.value,
                                    thickness=thickness,
                                    grit=grit,
                                    current_price=current_price,
                                    new_price=new_price,
                                    price_change=new_price - current_price,
                                ))
                                analysis.updated += 1
                                analysis.pending_changes.append({
                                    "type": "grinding",
                                    "action": "update",
                                    "id": existing.id,
                                    "price": new_price,
                                })
                        else:
                            analysis.items.append(ImportDiffItem(
                                row_number=row_number,
                                change_type="added",
                                data_type="grinding",
                                provider=current_provider.value,
                                thickness=thickness,
                                grit=grit,
                                new_price=new_price,
                            ))
                            analysis.added += 1
                            analysis.pending_changes.append({
                                "type": "grinding",
                                "action": "add",
                                "provider": current_provider.value,
                                "thickness": thickness,
                                "grit": grit,
                                "with_sb": with_sb,
                                "price": new_price,
                            })

    def _analyze_film_prices(self, df: pd.DataFrame, analysis: ImportAnalysis):
        """Analizuj ceny folii i wygeneruj diff."""
        # Sprawdz czy to format eksportu (tabela z naglowkami) czy oryginalny format
        first_row = [str(v).lower() for v in df.iloc[0].tolist() if pd.notna(v)]

        if any("typ folii" in col for col in first_row):
            # Format eksportu - tabela z kolumnami
            self._analyze_film_export_format(df, analysis)
        else:
            # Oryginalny format DANE FOLIA
            self._analyze_film_original_format(df, analysis)

    def _analyze_film_export_format(self, df: pd.DataFrame, analysis: ImportAnalysis):
        """Analizuj cennik folii w formacie eksportu."""
        raw_headers = [str(h).strip() for h in df.iloc[0].tolist()]
        df = df.iloc[1:].copy()
        df.columns = raw_headers

        headers_lower = {h.lower(): h for h in raw_headers}

        def find_col(patterns):
            for p in patterns:
                if p in headers_lower:
                    return headers_lower[p]
            return None

        film_type_col = find_col(["typ folii", "film_type", "typ"])
        thickness_col = find_col(["grubosc (mm)", "grubosc", "thickness"])
        price_col = find_col(["cena pln/kg", "cena", "price"])

        if not film_type_col:
            analysis.warnings.append(f"Folia: nie znaleziono kolumny 'Typ folii'. Dostepne: {raw_headers[:8]}")
            return

        # Pre-load cen folii do pamieci
        film_map = {}
        for fp in self.db.query(FilmPrice).all():
            key = (fp.film_type.value, fp.thickness)
            film_map[key] = fp

        for idx, row in df.iterrows():
            row_number = idx + 1
            try:
                film_type_str = str(row.get(film_type_col, "")).strip()
                if not film_type_str or film_type_str == "nan":
                    continue

                try:
                    film_type = FilmType(film_type_str)
                except ValueError:
                    # Sprobuj dopasowac po nazwie
                    film_type = None
                    for ft in FilmType:
                        if ft.value.lower() == film_type_str.lower():
                            film_type = ft
                            break
                    if not film_type:
                        continue

                thickness = float(row.get(thickness_col, 0)) if thickness_col else 0
                new_price = row.get(price_col) if price_col else None

                if pd.isna(new_price):
                    continue
                new_price = float(new_price)

                # Sprawdz istniejaca cene w pamieci
                key = (film_type.value, thickness)
                existing = film_map.get(key)

                if existing:
                    current_price = existing.price_pln_per_kg
                    if abs(current_price - new_price) < 0.001:
                        analysis.unchanged += 1
                    else:
                        analysis.items.append(ImportDiffItem(
                            row_number=row_number,
                            change_type="updated",
                            data_type="film",
                            film_type=film_type.value,
                            thickness=thickness,
                            current_price=current_price,
                            new_price=new_price,
                            price_change=new_price - current_price,
                        ))
                        analysis.updated += 1
                        analysis.pending_changes.append({
                            "type": "film",
                            "action": "update",
                            "id": existing.id,
                            "price": new_price,
                        })
                else:
                    analysis.items.append(ImportDiffItem(
                        row_number=row_number,
                        change_type="added",
                        data_type="film",
                        film_type=film_type.value,
                        thickness=thickness,
                        new_price=new_price,
                    ))
                    analysis.added += 1
                    analysis.pending_changes.append({
                        "type": "film",
                        "action": "add",
                        "film_type": film_type.value,
                        "thickness": thickness,
                        "price": new_price,
                    })
            except Exception as e:
                analysis.errors.append({"row": row_number, "error": str(e)})

    def _analyze_film_original_format(self, df: pd.DataFrame, analysis: ImportAnalysis):
        """Analizuj cennik folii w oryginalnym formacie DANE FOLIA."""
        # Znajdz wiersz naglowkowy
        header_row = None
        for idx, row in df.iterrows():
            if any("Novacel" in str(v) or "FOLIA" in str(v) or "Nitto" in str(v)
                   for v in row if pd.notna(v)):
                header_row = idx
                break

        if header_row is None:
            analysis.warnings.append("Nie znaleziono naglowkow folii w oryginalnym formacie")
            return

        # Pobierz naglowki
        headers = {}
        for col_idx, val in enumerate(df.iloc[header_row]):
            val_str = str(val).strip()
            if val_str in EXCEL_FILM_MAPPING:
                headers[col_idx] = EXCEL_FILM_MAPPING[val_str]

        # Parsuj ceny
        for idx in range(header_row + 1, len(df)):
            row_number = idx + 1
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
                        new_price = float(price_val)

                        # Sprawdz istniejaca cene
                        existing = self.db.query(FilmPrice).filter(
                            FilmPrice.film_type == film_type,
                            FilmPrice.thickness == thickness,
                        ).first()

                        if existing:
                            current_price = existing.price_pln_per_kg
                            if abs(current_price - new_price) < 0.001:
                                analysis.unchanged += 1
                            else:
                                analysis.items.append(ImportDiffItem(
                                    row_number=row_number,
                                    change_type="updated",
                                    data_type="film",
                                    film_type=film_type.value,
                                    thickness=thickness,
                                    current_price=current_price,
                                    new_price=new_price,
                                    price_change=new_price - current_price,
                                ))
                                analysis.updated += 1
                                analysis.pending_changes.append({
                                    "type": "film",
                                    "action": "update",
                                    "id": existing.id,
                                    "price": new_price,
                                })
                        else:
                            analysis.items.append(ImportDiffItem(
                                row_number=row_number,
                                change_type="added",
                                data_type="film",
                                film_type=film_type.value,
                                thickness=thickness,
                                new_price=new_price,
                            ))
                            analysis.added += 1
                            analysis.pending_changes.append({
                                "type": "film",
                                "action": "add",
                                "film_type": film_type.value,
                                "thickness": thickness,
                                "price": new_price,
                            })
                    except (ValueError, TypeError):
                        pass

    def apply_import(self, analysis: ImportAnalysis, mode: str = "update_existing") -> ImportResult:
        """Zastosuj zmiany z analizy.

        Args:
            analysis: Wynik analizy z analyze_file()
            mode: Tryb importu:
                - update_existing: tylko aktualizuj istniejace
                - add_new: tylko dodaj nowe
                - full_sync: aktualizuj + dodaj

        Returns:
            ImportResult: Wynik importu
        """
        if not self.db:
            raise ValueError("Brak polaczenia z baza danych")

        result = ImportResult()

        for change in analysis.pending_changes:
            try:
                if change["action"] == "update":
                    if mode in ("update_existing", "full_sync"):
                        if change["type"] == "base_price":
                            price = self.db.query(BasePrice).filter(
                                BasePrice.id == change["id"]
                            ).first()
                            if price:
                                price.price_pln_per_kg = change["price"]
                                result.base_prices_imported += 1
                        elif change["type"] == "grinding":
                            price = self.db.query(GrindingPrice).filter(
                                GrindingPrice.id == change["id"]
                            ).first()
                            if price:
                                price.price_pln_per_kg = change["price"]
                                result.grinding_prices_imported += 1
                        elif change["type"] == "film":
                            price = self.db.query(FilmPrice).filter(
                                FilmPrice.id == change["id"]
                            ).first()
                            if price:
                                price.price_pln_per_kg = change["price"]
                                result.film_prices_imported += 1

                elif change["action"] == "add":
                    if mode in ("add_new", "full_sync"):
                        if change["type"] == "base_price":
                            material_id = change.get("material_id")
                            if not material_id:
                                # Stworz material jesli nie istnieje
                                material = self._get_or_create_material(change["grade"])
                                material_id = material.id

                            bp = BasePrice(
                                material_id=material_id,
                                surface_finish=change["surface_finish"],
                                thickness=change["thickness"],
                                width=change["width"],
                                length=change["width"] * 2,
                                price_pln_per_kg=change["price"],
                            )
                            self.db.add(bp)
                            result.base_prices_imported += 1

                        elif change["type"] == "grinding":
                            gp = GrindingPrice(
                                provider=GrindingProvider(change["provider"]),
                                grit=change["grit"],
                                thickness=change["thickness"],
                                with_sb=change.get("with_sb", False),
                                width_variant=change.get("width_variant"),
                                price_pln_per_kg=change["price"],
                            )
                            self.db.add(gp)
                            result.grinding_prices_imported += 1

                        elif change["type"] == "film":
                            fp = FilmPrice(
                                film_type=FilmType(change["film_type"]),
                                thickness=change["thickness"],
                                price_pln_per_kg=change["price"],
                            )
                            self.db.add(fp)
                            result.film_prices_imported += 1

            except Exception as e:
                result.errors.append({
                    "change": change,
                    "error": str(e),
                })
                result.success = False

        self.db.commit()
        return result

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
