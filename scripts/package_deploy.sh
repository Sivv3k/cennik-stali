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

echo "=== Pakowanie Cennik BTH do wdrozenia ==="
echo ""

# Wczytaj konfiguracje z .syno_docker
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
    echo "Konfiguracja z .syno_docker:"
    echo "  Sciezka: $SYNOLOGY_PATH"
    echo "  PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
    echo "  Port: $APP_PORT"
    echo "  Siec: $DOCKER_NETWORK"
    echo ""
else
    echo "BLAD: Brak pliku .syno_docker"
    exit 1
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

echo "2. Generowanie docker-compose.yml..."
cat > "$PACKAGE_DIR/docker-compose.yml" << EOF
version: '3.8'

services:
  cennik-stali:
    build: .
    container_name: $CONTAINER_NAME
    restart: unless-stopped
    ports:
      - "$APP_PORT:8000"
    volumes:
      - $SYNOLOGY_PATH/data:/app/data
    environment:
      - APP_NAME=$APP_NAME
      - DEBUG=false
      - SECRET_KEY=\${SECRET_KEY}
      - DATABASE_URL=\${DATABASE_URL}
    env_file:
      - .env
    networks:
      - $DOCKER_NETWORK
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  $DOCKER_NETWORK:
    external: true
EOF

echo "3. Kopiowanie Dockerfile..."
cp "$DEPLOY_DIR/Dockerfile" "$PACKAGE_DIR/"

echo "4. Generowanie .env..."
SECRET_KEY=$(openssl rand -hex 32)
cat > "$PACKAGE_DIR/.env" << EOF
SECRET_KEY=$SECRET_KEY
DATABASE_URL=$DATABASE_URL
EOF

echo "5. Kopiowanie instrukcji..."
cp "$OUTPUT_DIR/INSTALL.md" "$PACKAGE_DIR/"

echo "6. Tworzenie katalogu data..."
mkdir -p "$PACKAGE_DIR/data/imports"
mkdir -p "$PACKAGE_DIR/data/exports"

echo "7. Tworzenie archiwum..."
cd "$TEMP_DIR"
tar -czvf "$OUTPUT_DIR/$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME" > /dev/null

echo "8. Sprzatanie..."
rm -rf "$TEMP_DIR"

echo ""
echo "=== Gotowe! ==="
echo "Archiwum: $OUTPUT_DIR/$PACKAGE_NAME.tar.gz"
echo ""
echo "Nastepne kroki:"
echo ""
echo "1. Skopiuj na Synology:"
echo "   scp $OUTPUT_DIR/$PACKAGE_NAME.tar.gz user@synology:/volume2/docker/"
echo ""
echo "2. Na Synology (SSH):"
echo "   cd /volume2/docker"
echo "   tar -xzvf $PACKAGE_NAME.tar.gz"
echo "   mv $PACKAGE_NAME cennik"
echo ""
echo "3. Portainer:"
echo "   Stacks → Add stack → Upload → /volume2/docker/cennik"
echo ""
echo "4. NPM:"
echo "   Proxy Host → cennik-stali:8000 → SSL"
echo ""
