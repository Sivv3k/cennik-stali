"""Endpointy do importu/eksportu danych."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.excel_import import ExcelImporter

router = APIRouter(prefix="/api/import", tags=["import-export"])

UPLOAD_DIR = Path("data/imports")


@router.post("/excel")
async def import_excel(
    file: UploadFile = File(..., description="Plik Excel do importu"),
    db: Session = Depends(get_db),
):
    """Importuj dane z pliku Excel."""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Nieprawidłowy format pliku. Wymagany: .xlsx lub .xls",
        )

    # Zapisz plik
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Importuj dane
    try:
        importer = ExcelImporter(db)
        result = importer.import_file(file_path)
        return {
            "status": "success",
            "filename": file.filename,
            "imported": result,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Błąd importu: {str(e)}")


@router.get("/preview/{filename}")
async def preview_excel(filename: str):
    """Podgląd struktury pliku Excel przed importem."""
    file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Plik nie znaleziony")

    try:
        importer = ExcelImporter(None)
        preview = importer.preview_file(file_path)
        return preview
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Błąd odczytu: {str(e)}")
