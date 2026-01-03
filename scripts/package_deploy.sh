#!/bin/bash
# Skrypt do pakowania aplikacji do wdrozenia na Synology
# Uzycie: ./scripts/package_deploy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$PROJECT_DIR/deploy/cennik"
OUTPUT_DIR="$PROJECT_DIR/deploy"
PACKAGE_NAME="cennik-stali-deploy"

echo "=== Pakowanie Cennik Stali do wdrozenia ==="
echo "Katalog projektu: $PROJECT_DIR"
echo ""

# Przejdz do katalogu projektu
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
cp "$DEPLOY_DIR/.env" "$PACKAGE_DIR/"

echo "3. Kopiowanie instrukcji..."
cp "$OUTPUT_DIR/INSTALL.md" "$PACKAGE_DIR/"

echo "4. Tworzenie katalogu data..."
mkdir -p "$PACKAGE_DIR/data/imports"
mkdir -p "$PACKAGE_DIR/data/exports"

echo "5. Generowanie SECRET_KEY..."
SECRET_KEY=$(openssl rand -hex 32)
sed -i.bak "s/ZMIEN_NA_LOSOWY_KLUCZ_32_ZNAKI/$SECRET_KEY/" "$PACKAGE_DIR/.env"
rm -f "$PACKAGE_DIR/.env.bak"

echo "6. Tworzenie archiwum..."
cd "$TEMP_DIR"
tar -czvf "$OUTPUT_DIR/$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME"

echo "7. Sprzatanie..."
rm -rf "$TEMP_DIR"

echo ""
echo "=== Gotowe! ==="
echo "Archiwum: $OUTPUT_DIR/$PACKAGE_NAME.tar.gz"
echo ""
echo "Nastepne kroki:"
echo "1. Skopiuj archiwum na Synology:"
echo "   scp $OUTPUT_DIR/$PACKAGE_NAME.tar.gz user@synology:/volume2/docker/"
echo ""
echo "2. Na Synology rozpakuj i uruchom:"
echo "   cd /volume2/docker"
echo "   tar -xzvf $PACKAGE_NAME.tar.gz"
echo "   cd $PACKAGE_NAME"
echo "   docker-compose up -d --build"
echo ""
