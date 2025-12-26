# Cennik Stali

System cennikowy dla materiałów stalowych i aluminiowych.

## Funkcjonalności

- Cennik tabelaryczny dla różnych gatunków materiałów:
  - Stal nierdzewna (304, 316, 430, etc.)
  - Stal czarna (DC01, S235, S355, etc.)
  - Aluminium (1050, 5754, 6061, etc.)
- Uwzględnienie parametrów:
  - Grubość blachy
  - Typ powierzchni (2B, BA, No.4, szczotkowana)
  - Obróbka wykańczająca (szlifowanie, polerowanie)
  - Zabezpieczenie (folia ochronna)
  - Źródło: zwoje CTL, multiblanking
- Import danych z plików Excel
- API REST
- Interaktywny interfejs webowy

## Instalacja

```bash
# Klonowanie repozytorium
git clone https://github.com/YOUR_USERNAME/cennik-stali.git
cd cennik-stali

# Utworzenie środowiska wirtualnego
python -m venv venv
source venv/bin/activate  # Linux/Mac
# lub: venv\Scripts\activate  # Windows

# Instalacja zależności
pip install -r requirements.txt

# Konfiguracja
cp .env.example .env
# Edytuj .env według potrzeb

# Uruchomienie
uvicorn src.main:app --reload
```

## Struktura projektu

```
cennik-stali/
├── src/
│   ├── main.py           # Aplikacja FastAPI
│   ├── config.py         # Konfiguracja
│   ├── database.py       # Połączenie z bazą danych
│   ├── models/           # Modele SQLAlchemy
│   ├── schemas/          # Schematy Pydantic
│   ├── routers/          # Endpointy API
│   ├── services/         # Logika biznesowa
│   └── templates/        # Szablony HTML
├── static/               # Pliki statyczne
├── data/imports/         # Pliki Excel do importu
└── tests/                # Testy
```

## API

Po uruchomieniu dokumentacja API dostępna pod:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Licencja

MIT
