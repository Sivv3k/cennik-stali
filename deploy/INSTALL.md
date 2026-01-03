# Instalacja Cennik Stali na Synology

## Wymagania
- Synology NAS z Container Manager (Docker)
- SSH dostep do NAS
- Opcjonalnie: Portainer, Nginx Proxy Manager

## Szybka instalacja

### 1. Spakuj aplikacje (na komputerze lokalnym)

```bash
cd /sciezka/do/cennik-stali
./scripts/package_deploy.sh
```

To utworzy plik `deploy/cennik-stali-deploy.tar.gz` z wygenerowanym SECRET_KEY.

### 2. Skopiuj na Synology

```bash
scp deploy/cennik-stali-deploy.tar.gz user@synology:/volume1/docker/
```

### 3. Rozpakuj i uruchom (na Synology przez SSH)

```bash
ssh user@synology
cd /volume1/docker
tar -xzvf cennik-stali-deploy.tar.gz
cd cennik-stali-deploy

# Utworz siec proxy (jesli nie istnieje)
docker network create proxy 2>/dev/null || true

# Uruchom aplikacje
docker-compose up -d --build
```

### 4. Sprawdz status

```bash
# Logi
docker logs -f cennik-stali

# Health check
curl http://localhost:8080/health
```

## Dostep

- **Lokalnie**: http://synology-ip:8080
- **Admin**: admin / admin123 (zmien haslo przy pierwszym logowaniu!)

---

## Instalacja reczna (bez skryptu)

### 1. Przygotuj strukture na Synology

```bash
mkdir -p /volume1/docker/cennik-stali/data/imports
mkdir -p /volume1/docker/cennik-stali/data/exports
cd /volume1/docker/cennik-stali
```

### 2. Skopiuj pliki z komputera lokalnego

```bash
# Na komputerze lokalnym
scp -r src static alembic alembic.ini requirements.txt user@synology:/volume1/docker/cennik-stali/
scp deploy/cennik/Dockerfile deploy/cennik/docker-compose.yml deploy/cennik/.env user@synology:/volume1/docker/cennik-stali/
```

### 3. Skonfiguruj .env

```bash
# Na Synology
cd /volume1/docker/cennik-stali
nano .env
```

Wygeneruj i wklej SECRET_KEY:
```bash
openssl rand -hex 32
```

### 4. Uruchom

```bash
docker network create proxy 2>/dev/null || true
docker-compose up -d --build
```

---

## Konfiguracja Nginx Proxy Manager (opcjonalnie)

Jesli uzywasz NPM do SSL/reverse proxy:

1. Hosts → Proxy Hosts → Add Proxy Host
2. Wypelnij:

| Pole | Wartosc |
|------|---------|
| Domain Names | cennik.twoja-domena.pl |
| Scheme | http |
| Forward Hostname / IP | cennik-stali |
| Forward Port | 8000 |
| Websockets Support | ON |

3. SSL → Request new SSL Certificate → Force SSL

---

## PostgreSQL (opcjonalnie)

Domyslnie aplikacja uzywa SQLite (plik w `data/cennik.db`).

Aby uzyc PostgreSQL:

1. Edytuj `.env`:
```
DATABASE_URL=postgresql://cennik_user:haslo@host:port/cennik_stali
```

2. Edytuj `docker-compose.yml`:
```yaml
environment:
  # Zakomentuj SQLite
  # - DATABASE_URL=sqlite:///./data/cennik.db
  # Odkomentuj PostgreSQL
  - DATABASE_URL=${DATABASE_URL}
```

3. Utworz baze na PostgreSQL:
```sql
CREATE DATABASE cennik_stali ENCODING 'UTF8';
CREATE USER cennik_user WITH PASSWORD 'silne_haslo';
GRANT ALL PRIVILEGES ON DATABASE cennik_stali TO cennik_user;
```

---

## Komendy administracyjne

```bash
# Restart
docker restart cennik-stali

# Logi (follow)
docker logs -f cennik-stali

# Zatrzymaj
docker-compose down

# Rebuild po aktualizacji
docker-compose down
docker-compose up -d --build

# Wejdz do kontenera
docker exec -it cennik-stali /bin/bash
```

---

## Backup

```bash
# Kopia bazy SQLite
cp /volume1/docker/cennik-stali/data/cennik.db /volume1/backup/cennik_$(date +%Y%m%d).db

# Kopia calej aplikacji
tar -czvf /volume1/backup/cennik-stali-backup-$(date +%Y%m%d).tar.gz /volume1/docker/cennik-stali/
```

---

## Rozwiazywanie problemow

### Kontener nie startuje
```bash
docker logs cennik-stali
```

### Brak dostepu do portu 8080
```bash
# Sprawdz czy port jest zajety
netstat -tlnp | grep 8080

# Zmien port w docker-compose.yml
ports:
  - "8081:8000"  # uzyj innego portu
```

### Blad bazy danych
```bash
# Sprawdz uprawnienia
ls -la /volume1/docker/cennik-stali/data/

# Napraw uprawnienia
chown -R 1000:1000 /volume1/docker/cennik-stali/data/
```

### Reset hasla admina
```bash
docker exec -it cennik-stali python -c "
from src.database import SessionLocal
from src.models.user import User
import bcrypt
db = SessionLocal()
admin = db.query(User).filter(User.username == 'admin').first()
admin.hashed_password = bcrypt.hashpw('nowehaslo123'.encode(), bcrypt.gensalt()).decode()
db.commit()
print('Haslo zmienione na: nowehaslo123')
"
```
