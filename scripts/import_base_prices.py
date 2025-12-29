"""Import cen bazowych z Excela do bazy danych."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.database import SessionLocal, init_db
from src.models import Material, MaterialCategory, BasePrice


# Mapowanie gatunkow
GRADE_CONFIG = {
    1.4301: {
        "name": "Stal nierdzewna 304",
        "category": MaterialCategory.STAINLESS_STEEL,
        "density": 7.9,
        "equivalent_grades": "AISI 304, X5CrNi18-10",
    },
    1.4404: {
        "name": "Stal nierdzewna 316L",
        "category": MaterialCategory.STAINLESS_STEEL,
        "density": 8.0,
        "equivalent_grades": "AISI 316L, X2CrNiMo17-12-2",
    },
    1.4016: {
        "name": "Stal nierdzewna 430",
        "category": MaterialCategory.STAINLESS_STEEL,
        "density": 7.7,
        "equivalent_grades": "AISI 430, X6Cr17",
    },
}


def import_base_prices():
    """Import base prices from Excel."""

    init_db()
    db = SessionLocal()

    # Read Excel
    xl = pd.ExcelFile('data/imports/Kopia CENNIK NOWY.xlsx')
    df = pd.read_excel(xl, sheet_name='cennik baza', header=0)

    # Clear existing data
    db.query(BasePrice).delete()
    db.query(Material).delete()
    db.commit()
    print("Wyczyszczono istniejace dane materialow i cen bazowych")

    # Create materials
    materials = {}
    for grade_num, config in GRADE_CONFIG.items():
        grade_str = str(grade_num)
        material = Material(
            name=config["name"],
            grade=grade_str,
            category=config["category"],
            density=config["density"],
            equivalent_grades=config["equivalent_grades"],
        )
        db.add(material)
        db.flush()
        materials[grade_num] = material
        print(f"  Utworzono material: {config['name']} ({grade_str})")

    print(f"\nUtworzono {len(materials)} materialow")

    # Import base prices
    count = 0
    skipped = 0

    for idx, row in df.iterrows():
        grade = row['Gatunek ']
        surface = row['powierzchnia']
        thickness = row['grubość']
        width = row['szerokość']
        length = row['długość ']
        base_price = row['z papierem']

        # Skip rows with missing data
        if pd.isna(base_price) or pd.isna(thickness) or pd.isna(width) or pd.isna(length):
            skipped += 1
            continue

        if grade not in materials:
            skipped += 1
            continue

        bp = BasePrice(
            material_id=materials[grade].id,
            surface_finish=str(surface),
            thickness=float(thickness),
            width=float(width),
            length=float(length),
            price_pln_per_kg=float(base_price),
        )
        db.add(bp)
        count += 1

    db.commit()
    print(f"\n=== SUKCES: Zaimportowano {count} cen bazowych (pominieto {skipped}) ===")

    # Statystyki
    print("\nStatystyki per gatunek:")
    for grade_num, material in materials.items():
        total = db.query(BasePrice).filter(BasePrice.material_id == material.id).count()
        print(f"  {material.grade}: {total} cen")

    print("\nStatystyki per powierzchnie:")
    surfaces = db.query(BasePrice.surface_finish).distinct().all()
    for (surface,) in surfaces:
        total = db.query(BasePrice).filter(BasePrice.surface_finish == surface).count()
        print(f"  {surface}: {total} cen")

    db.close()


if __name__ == "__main__":
    import_base_prices()
