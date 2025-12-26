"""Serwis do importu danych z plików Excel."""

from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session


class ExcelImporter:
    """Importer danych z plików Excel."""

    def __init__(self, db: Optional[Session]):
        self.db = db

    def preview_file(self, file_path: Path) -> dict[str, Any]:
        """Podgląd struktury pliku Excel."""
        xl = pd.ExcelFile(file_path)

        preview = {
            "filename": file_path.name,
            "sheets": [],
        }

        for sheet_name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet_name, nrows=5)
            preview["sheets"].append({
                "name": sheet_name,
                "columns": list(df.columns),
                "rows_preview": df.head().to_dict(orient="records"),
                "total_rows": len(pd.read_excel(xl, sheet_name=sheet_name)),
            })

        return preview

    def import_file(self, file_path: Path) -> dict[str, Any]:
        """Importuj dane z pliku Excel.

        TODO: Ta metoda wymaga dostosowania do struktury Twoich plików Excel.
        Po wgraniu przykładowych plików, zaimplementuję właściwy parsing.
        """
        if not self.db:
            raise ValueError("Brak połączenia z bazą danych")

        xl = pd.ExcelFile(file_path)
        result = {
            "sheets_processed": 0,
            "materials_imported": 0,
            "prices_imported": 0,
            "errors": [],
        }

        for sheet_name in xl.sheet_names:
            try:
                df = pd.read_excel(xl, sheet_name=sheet_name)
                result["sheets_processed"] += 1

                # TODO: Implementacja parsingu po analizie struktury plików
                # self._process_sheet(df, sheet_name, result)

            except Exception as e:
                result["errors"].append({
                    "sheet": sheet_name,
                    "error": str(e),
                })

        return result

    def _process_sheet(
        self, df: pd.DataFrame, sheet_name: str, result: dict
    ) -> None:
        """Przetwórz pojedynczy arkusz.

        TODO: Implementacja po analizie struktury plików Excel.
        """
        pass
