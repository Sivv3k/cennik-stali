"""Import danych szlifu z Excela do bazy danych."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.database import SessionLocal, init_db
from src.models import GrindingPrice, GrindingProvider

# Standard thicknesses for matrix
STANDARD_THICKNESSES = [
    0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0
]

def import_grinding_data():
    """Import grinding prices from Excel."""

    # Setup database
    init_db()
    db = SessionLocal()

    # Read Excel
    xl = pd.ExcelFile('data/imports/Kopia CENNIK NOWY.xlsx')
    df = pd.read_excel(xl, sheet_name='DANE SZLIF', header=None)

    count = 0

    # Clear existing data
    db.query(GrindingPrice).delete()
    db.commit()
    print("Wyczyszczono istniejace dane szlifu")

    # === CAMU ===
    print("\n=== Import CAMU ===")
    camu_data = {
        0.4: {'K320/K400': 0.59, 'K320/K400_sb': 0.70, 'K240/K180': 0.76, 'K240/K180_sb': 0.76, 'K80/K120': 1.64},
        0.5: {'K320/K400': 0.56, 'K320/K400_sb': 0.68, 'K240/K180': 0.73, 'K240/K180_sb': 0.73, 'K80/K120': 1.58},
        0.6: {'K320/K400': 0.52, 'K320/K400_sb': 0.62, 'K240/K180': 0.68, 'K240/K180_sb': 0.68, 'K80/K120': 1.46},
        0.7: {'K320/K400': 0.46, 'K320/K400_sb': 0.55, 'K240/K180': 0.59, 'K240/K180_sb': 0.59, 'K80/K120': 1.28},
        0.8: {'K320/K400': 0.40, 'K320/K400_sb': 0.47, 'K240/K180': 0.51, 'K240/K180_sb': 0.51, 'K80/K120': 1.10},
        1.0: {'K320/K400': 0.38, 'K320/K400_sb': 0.45, 'K240/K180': 0.49, 'K240/K180_sb': 0.49, 'K80/K120': 1.06},
        1.2: {'K320/K400': 0.36, 'K320/K400_sb': 0.44, 'K240/K180': 0.47, 'K240/K180_sb': 0.47, 'K80/K120': 1.02},
        1.5: {'K320/K400': 0.36, 'K320/K400_sb': 0.43, 'K240/K180': 0.46, 'K240/K180_sb': 0.46, 'K80/K120': 1.00},
        2.0: {'K320/K400': 0.34, 'K320/K400_sb': 0.41, 'K240/K180': 0.44, 'K240/K180_sb': 0.44, 'K80/K120': 0.96},
        2.5: {'K320/K400': 0.33, 'K320/K400_sb': 0.40, 'K240/K180': 0.43, 'K240/K180_sb': 0.43, 'K80/K120': 0.94},
        3.0: {'K320/K400': 0.32, 'K320/K400_sb': 0.39, 'K240/K180': 0.42, 'K240/K180_sb': 0.42, 'K80/K120': 0.90},
    }

    for thickness in STANDARD_THICKNESSES:
        for grit_key in ['K320/K400', 'K320/K400_sb', 'K240/K180', 'K240/K180_sb', 'K80/K120']:
            with_sb = '_sb' in grit_key
            grit = grit_key.replace('_sb', '')

            if thickness in camu_data and grit_key in camu_data[thickness]:
                price = camu_data[thickness][grit_key]
            else:
                price = 0  # Zablokowane

            gp = GrindingPrice(
                provider=GrindingProvider.CAMU,
                grit=grit,
                thickness=thickness,
                price_pln_per_kg=price,
                with_sb=with_sb,
                width_variant=None,
            )
            db.add(gp)
            count += 1

    print(f"  Dodano {count} wpisow CAMU")

    # === BABCIA ===
    print("\n=== Import BABCIA ===")
    babcia_data = {
        0.4: {'K320/K400': 1.18, 'K320/K400_sb': 1.40, 'K240/K180': 1.52, 'K240/K180_sb': 1.52, 'K80/K120': 1.64},
        0.5: {'K320/K400': 1.12, 'K320/K400_sb': 1.36, 'K240/K180': 1.46, 'K240/K180_sb': 1.46, 'K80/K120': 1.58},
        0.6: {'K320/K400': 1.04, 'K320/K400_sb': 1.24, 'K240/K180': 1.36, 'K240/K180_sb': 1.36, 'K80/K120': 1.46},
        0.7: {'K320/K400': 0.92, 'K320/K400_sb': 1.10, 'K240/K180': 1.18, 'K240/K180_sb': 1.18, 'K80/K120': 1.28},
        0.8: {'K320/K400': 0.80, 'K320/K400_sb': 0.94, 'K240/K180': 1.02, 'K240/K180_sb': 1.02, 'K80/K120': 1.10},
        1.0: {'K320/K400': 0.76, 'K320/K400_sb': 0.90, 'K240/K180': 0.98, 'K240/K180_sb': 0.98, 'K80/K120': 1.06},
        1.2: {'K320/K400': 0.72, 'K320/K400_sb': 0.88, 'K240/K180': 0.94, 'K240/K180_sb': 0.94, 'K80/K120': 1.02},
        1.5: {'K320/K400': 0.72, 'K320/K400_sb': 0.86, 'K240/K180': 0.92, 'K240/K180_sb': 0.92, 'K80/K120': 1.00},
        2.0: {'K320/K400': 0.68, 'K320/K400_sb': 0.82, 'K240/K180': 0.88, 'K240/K180_sb': 0.88, 'K80/K120': 0.96},
        2.5: {'K320/K400': 0.66, 'K320/K400_sb': 0.80, 'K240/K180': 0.86, 'K240/K180_sb': 0.86, 'K80/K120': 0.94},
        3.0: {'K320/K400': 0.64, 'K320/K400_sb': 0.78, 'K240/K180': 0.84, 'K240/K180_sb': 0.84, 'K80/K120': 0.90},
    }

    babcia_count = 0
    for thickness in STANDARD_THICKNESSES:
        for grit_key in ['K320/K400', 'K320/K400_sb', 'K240/K180', 'K240/K180_sb', 'K80/K120']:
            with_sb = '_sb' in grit_key
            grit = grit_key.replace('_sb', '')

            if thickness in babcia_data and grit_key in babcia_data[thickness]:
                price = babcia_data[thickness][grit_key]
            else:
                price = 0  # Zablokowane

            gp = GrindingPrice(
                provider=GrindingProvider.BABCIA,
                grit=grit,
                thickness=thickness,
                price_pln_per_kg=price,
                with_sb=with_sb,
                width_variant=None,
            )
            db.add(gp)
            babcia_count += 1

    print(f"  Dodano {babcia_count} wpisow BABCIA")
    count += babcia_count

    # === BORYS ===
    print("\n=== Import BORYS ===")
    borys_x1000 = {
        0.4: 1.149, 0.5: 1.024, 0.6: 0.941, 0.8: 0.84, 1.0: 0.78,
        1.2: 0.732, 1.5: 0.724, 2.0: 0.68, 3.0: 0.68, 4.0: 0.85,
        5.0: 0.85, 6.0: 0.85, 8.0: 4.0, 10.0: 4.0,
    }
    borys_x2000 = {
        1.0: 4.0, 1.2: 3.9, 1.5: 3.5, 2.0: 2.3, 3.0: 2.3, 4.0: 2.3,
        5.0: 2.3, 6.0: 2.3, 8.0: 4.5, 10.0: 4.5,
    }

    borys_count = 0
    for thickness in STANDARD_THICKNESSES:
        # x1000/1250/1500
        price_x1000 = borys_x1000.get(thickness, 0)
        gp = GrindingPrice(
            provider=GrindingProvider.BORYS,
            grit=None,
            thickness=thickness,
            price_pln_per_kg=price_x1000,
            with_sb=False,
            width_variant="x1000/1250/1500",
        )
        db.add(gp)
        borys_count += 1

        # x2000
        price_x2000 = borys_x2000.get(thickness, 0)
        gp = GrindingPrice(
            provider=GrindingProvider.BORYS,
            grit=None,
            thickness=thickness,
            price_pln_per_kg=price_x2000,
            with_sb=False,
            width_variant="x2000",
        )
        db.add(gp)
        borys_count += 1

    print(f"  Dodano {borys_count} wpisow BORYS")
    count += borys_count

    # === COSTA (na podstawie BABCIA, 0.8-6mm) ===
    print("\n=== Import COSTA (na podstawie BABCIA, 0.8-6mm) ===")
    costa_count = 0
    for thickness in STANDARD_THICKNESSES:
        for grit_key in ['K320/K400', 'K320/K400_sb', 'K240/K180', 'K240/K180_sb', 'K80/K120']:
            with_sb = '_sb' in grit_key
            grit = grit_key.replace('_sb', '')

            # COSTA dziala tylko dla 0.8-6mm
            if 0.8 <= thickness <= 6.0 and thickness in babcia_data and grit_key in babcia_data[thickness]:
                price = babcia_data[thickness][grit_key]
            else:
                price = 0  # Zablokowane

            gp = GrindingPrice(
                provider=GrindingProvider.COSTA,
                grit=grit,
                thickness=thickness,
                price_pln_per_kg=price,
                with_sb=with_sb,
                width_variant=None,
            )
            db.add(gp)
            costa_count += 1

    print(f"  Dodano {costa_count} wpisow COSTA")
    count += costa_count

    db.commit()
    print(f"\n=== SUKCES: Zaimportowano {count} wpisow szlifu ===")

    # Statystyki
    print("\nStatystyki:")
    for provider in GrindingProvider:
        total = db.query(GrindingPrice).filter(GrindingPrice.provider == provider).count()
        available = db.query(GrindingPrice).filter(
            GrindingPrice.provider == provider,
            GrindingPrice.price_pln_per_kg > 0
        ).count()
        blocked = total - available
        print(f"  {provider.value}: {total} wpisow ({available} dostepnych, {blocked} zablokowanych)")

    db.close()


if __name__ == "__main__":
    import_grinding_data()
