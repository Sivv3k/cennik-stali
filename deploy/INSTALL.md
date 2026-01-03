# Instalacja Cennik BTH na Synology (Portainer + NPM)

## Konfiguracja

| Parametr | Wartosc |
|----------|---------|
| Sciezka | /volume2/docker/cennik |
| PostgreSQL | 172.16.10.201:2665 |
| Baza | cennik_stali |
| User | cennik_user |
| Port | 23456 |
| Siec Docker | si_br |

---

## 1. Przygotowanie PostgreSQL

```bash
psql -h 172.16.10.201 -p 2665 -U postgres
```

```sql
CREATE DATABASE cennik_stali ENCODING 'UTF8';
CREATE USER cennik_user WITH PASSWORD 'dupajaswegierskiszlachcic';
GRANT ALL PRIVILEGES ON DATABASE cennik_stali TO cennik_user;
\c cennik_stali
GRANT ALL ON SCHEMA public TO cennik_user;
```

---

## 2. Przygotowanie plikow

### Na komputerze lokalnym:

```bash
cd /sciezka/do/cennik-stali
./scripts/package_deploy.sh
```

### Skopiuj na Synology:

```bash
scp deploy/cennik-stali-deploy.tar.gz user@synology:/volume2/docker/
```

### Na Synology (SSH):

```bash
cd /volume2/docker
tar -xzvf cennik-stali-deploy.tar.gz
mv cennik-stali-deploy cennik
```

---

## 3. Wdrozenie przez Portainer

### 3.1 Sprawdz siec si_br

Portainer → Networks → sprawdz czy istnieje `si_br`

Jesli nie:
- Add network
- Name: `si_br`
- Driver: `bridge`

### 3.2 Utworz Stack

1. Portainer → **Stacks** → **Add stack**
2. Name: `cennik-bth`
3. Build method: **Repository** lub **Upload**

#### Opcja A: Upload (zalecane)

1. Wybierz **Upload**
2. Wskaz folder: `/volume2/docker/cennik`
3. Kliknij **Deploy the stack**

#### Opcja B: Web editor

1. Wybierz **Web editor**
2. Wklej zawartosc `docker-compose.yml`:

```yaml
version: '3.8'

services:
  cennik-stali:
    build: .
    container_name: cennik-stali
    restart: unless-stopped
    ports:
      - "23456:8000"
    volumes:
      - /volume2/docker/cennik/data:/app/data
    environment:
      - APP_NAME=Cennik BTH
      - DEBUG=false
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
    env_file:
      - .env
    networks:
      - si_br
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  si_br:
    external: true
```

3. W sekcji **Environment variables** dodaj:
   - `SECRET_KEY` = (wygeneruj: `openssl rand -hex 32`)
   - `DATABASE_URL` = `postgresql://cennik_user:dupajaswegierskiszlachcic@172.16.10.201:2665/cennik_stali`

4. Kliknij **Deploy the stack**

---

## 4. Konfiguracja NPM (Nginx Proxy Manager)

1. NPM → **Hosts** → **Proxy Hosts** → **Add Proxy Host**

2. Wypelnij **Details**:

| Pole | Wartosc |
|------|---------|
| Domain Names | cennik.bth-impost.pl (lub inna domena) |
| Scheme | http |
| Forward Hostname / IP | cennik-stali |
| Forward Port | 8000 |
| Cache Assets | OFF |
| Block Common Exploits | ON |
| Websockets Support | ON |

3. Zakladka **SSL**:
   - SSL Certificate: Request a new SSL Certificate
   - Force SSL: ON
   - HTTP/2 Support: ON
   - Email: twoj@email.pl

4. Kliknij **Save**

---

## 5. Weryfikacja

### Sprawdz logi w Portainer:
Containers → cennik-stali → Logs

### Test lokalny:
```bash
curl http://172.16.10.201:23456/health
```

### Test przez NPM:
```
https://cennik.bth-impost.pl
```

---

## Dostep

- **Lokalnie**: http://synology-ip:23456
- **Przez NPM**: https://cennik.bth-impost.pl
- **Login**: admin / admin123

---

## Komendy (Portainer)

| Akcja | Gdzie |
|-------|-------|
| Restart | Containers → cennik-stali → Restart |
| Logi | Containers → cennik-stali → Logs |
| Konsola | Containers → cennik-stali → Console |
| Rebuild | Stacks → cennik-bth → Editor → Update the stack |

### Lub przez SSH:

```bash
cd /volume2/docker/cennik
docker-compose down
docker-compose up -d --build
```

---

## Backup

```bash
# PostgreSQL
pg_dump -h 172.16.10.201 -p 2665 -U cennik_user cennik_stali > /volume2/backup/cennik_$(date +%Y%m%d).sql
```

---

## Troubleshooting

### Kontener nie startuje
- Portainer → Containers → cennik-stali → Logs
- Sprawdz czy siec `si_br` istnieje
- Sprawdz czy PostgreSQL jest dostepny

### NPM nie widzi kontenera
- Upewnij sie ze kontener i NPM sa w tej samej sieci (`si_br`)
- Uzyj nazwy kontenera `cennik-stali` zamiast IP

### Reset hasla admina
Portainer → Containers → cennik-stali → Console → /bin/bash

```bash
python -c "
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
