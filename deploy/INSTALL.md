# Instalacja Cennik Stali na Synology

## Wymagania
- Synology NAS z Container Manager (Docker)
- PostgreSQL na 172.16.10.201:2665
- SSH dostep do NAS

## Konfiguracja (z pliku .syno_docker)

| Parametr | Wartosc |
|----------|---------|
| Sciezka | /volume2/docker/cennik |
| PostgreSQL | 172.16.10.201:2665 |
| Baza | cennik_stali |
| User | cennik_user |
| Port aplikacji | 8080 |

---

## Szybka instalacja

### 1. Spakuj aplikacje (na komputerze lokalnym)

```bash
cd /sciezka/do/cennik-stali
./scripts/package_deploy.sh
```

### 2. Skopiuj na Synology

```bash
scp deploy/cennik-stali-deploy.tar.gz user@synology:/volume2/docker/
```

### 3. Rozpakuj i uruchom (na Synology przez SSH)

```bash
ssh user@synology
cd /volume2/docker
tar -xzvf cennik-stali-deploy.tar.gz
mv cennik-stali-deploy cennik
cd cennik

# Utworz siec proxy (jesli nie istnieje)
docker network create proxy 2>/dev/null || true

# Uruchom aplikacje
docker-compose up -d --build
```

### 4. Sprawdz status

```bash
docker logs -f cennik-stali
curl http://localhost:8080/health
```

## Dostep

- **URL**: http://synology-ip:8080
- **Admin**: admin / admin123

---

## Przygotowanie PostgreSQL

Przed pierwszym uruchomieniem utworz baze:

```bash
psql -h 172.16.10.201 -p 2665 -U postgres
```

```sql
CREATE DATABASE cennik_stali ENCODING 'UTF8';
CREATE USER cennik_user WITH PASSWORD 'silne_haslo_123';
GRANT ALL PRIVILEGES ON DATABASE cennik_stali TO cennik_user;
\c cennik_stali
GRANT ALL ON SCHEMA public TO cennik_user;
```

---

## Komendy

```bash
# Restart
docker restart cennik-stali

# Logi
docker logs -f cennik-stali

# Rebuild
cd /volume2/docker/cennik
docker-compose down
docker-compose up -d --build

# Wejdz do kontenera
docker exec -it cennik-stali /bin/bash
```

---

## Backup

```bash
# Backup PostgreSQL
pg_dump -h 172.16.10.201 -p 2665 -U cennik_user cennik_stali > /volume2/backup/cennik_$(date +%Y%m%d).sql
```

---

## Reset hasla admina

```bash
docker exec -it cennik-stali python -c "
from src.database import SessionLocal
from src.models.user import User
import bcrypt
db = SessionLocal()
admin = db.query(User).filter(User.username == 'admin').first()
admin.hashed_password = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
db.commit()
print('Haslo: admin123')
"
```
