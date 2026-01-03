#!/bin/bash
# Skrypt do pakowania aplikacji do wdrozenia na Synology
# Uzycie: ./scripts/package_deploy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$PROJECT_DIR/deploy/cennik"
OUTPUT_DIR="$PROJECT_DIR/deploy"
PACKAGE_NAME="cennik-stali-deploy"
CONFIG_FILE="$PROJECT_DIR/.syno_docker"

echo "=== Pakowanie Cennik Stali do wdrozenia ==="
echo ""

# Wczytaj konfiguracje z .syno_docker
if [ -f "$CONFIG_FILE" ]; then
    echo "Wczytywanie konfiguracji z .syno_docker..."
    source "$CONFIG_FILE"
    echo "  Sciezka Synology: $SYNOLOGY_PATH"
    echo "  PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT"
    echo "  Baza: $POSTGRES_DB"
    echo ""
else
    echo "UWAGA: Brak pliku .syno_docker - uzywam domyslnych wartosci"
    SYNOLOGY_PATH="/volume2/docker/cennik"
    DATABASE_URL="postgresql://cennik_user:silne_haslo_123@172.16.10.201:2665/cennik_stali"
fi

cd "$PROJECT_DIR"

# Utworz katalog tymczasowy
TEMP_DIR=$(mktemp -d)
PACKAGE_DIR="$TEMP_DIR/$PACKAGE_NAME"
mkdir -p "$PACKAGE_DIR"

echo "1. Kopiowanie plikow zrodlowych..."
cp -r src "$PACKAGE_DIR/"
cp -r static "$PACKAGE_DIR/"
cp -r alembic "$PACKAGE_DIR/"
cp alembic.ini "$PACKAGE_DIR/"
cp requirements.txt "$PACKAGE_DIR/"

echo "2. Kopiowanie plikow Docker..."
cp "$DEPLOY_DIR/Dockerfile" "$PACKAGE_DIR/"
cp "$DEPLOY_DIR/docker-compose.yml" "$PACKAGE_DIR/"

echo "3. Generowanie .env z konfiguracja..."
SECRET_KEY=$(openssl rand -hex 32)
cat > "$PACKAGE_DIR/.env" << EOF
SECRET_KEY=$SECRET_KEY
DATABASE_URL=$DATABASE_URL
EOF

echo "4. Kopiowanie instrukcji..."
cp "$OUTPUT_DIR/INSTALL.md" "$PACKAGE_DIR/"

echo "5. Tworzenie katalogu data..."
mkdir -p "$PACKAGE_DIR/data/imports"
mkdir -p "$PACKAGE_DIR/data/exports"

echo "6. Tworzenie archiwum..."
cd "$TEMP_DIR"
tar -czvf "$OUTPUT_DIR/$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME" > /dev/null

echo "7. Sprzatanie..."
rm -rf "$TEMP_DIR"

echo ""
echo "=== Gotowe! ==="
echo "Archiwum: $OUTPUT_DIR/$PACKAGE_NAME.tar.gz"
echo ""
echo "Nastepne kroki:"
echo "1. Skopiuj na Synology:"
echo "   scp $OUTPUT_DIR/$PACKAGE_NAME.tar.gz user@synology:$SYNOLOGY_PATH/../"
echo ""
echo "2. Na Synology:"
echo "   cd $SYNOLOGY_PATH/.."
echo "   tar -xzvf $PACKAGE_NAME.tar.gz"
echo "   mv $PACKAGE_NAME cennik"
echo "   cd cennik"
echo "   docker network create proxy 2>/dev/null || true"
echo "   docker-compose up -d --build"
echo ""
