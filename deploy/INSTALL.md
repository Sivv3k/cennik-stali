# Instalacja Cennik Stali na Synology

## Wymagania
- Synology NAS z Dockerem
- Portainer
- Nginx Proxy Manager
- Sieć Docker o nazwie `proxy`

## 1. Przygotowanie struktury

```bash
# Na Synology przez SSH
mkdir -p /volume2/docker/cennik/data/imports
mkdir -p /volume2/docker/cennik/data/exports
```

## 2. Skopiuj pliki

Skopiuj caly folder `cennik/` do `/volume2/docker/cennik/`:
- Dockerfile
- docker-compose.yml
- .env
- requirements.txt
- src/
- static/

```bash
# Z lokalnego komputera
scp -r deploy/cennik/* user@synology:/volume2/docker/cennik/
```

## 3. Skonfiguruj .env

```bash
# Na Synology
cd /volume2/docker/cennik
nano .env
```

Zmien `SECRET_KEY` na losowy ciag:
```
SECRET_KEY=wygenerowany_klucz_32_znaki
```

## 4. Utworz siec proxy (jesli nie istnieje)

W Portainer → Networks → Add network:
- Name: `proxy`
- Driver: `bridge`

Lub przez SSH:
```bash
docker network create proxy
```

## 5. Wdrozenie przez Portainer

1. Portainer → Stacks → Add stack
2. Name: `cennik-stali`
3. Build method: **Upload**
4. Upload folder: `/volume2/docker/cennik`
5. Lub Web editor - wklej zawartosc docker-compose.yml
6. Kliknij **Deploy the stack**

## 6. Konfiguracja Nginx Proxy Manager

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

## 7. Pierwsze uruchomienie

Aplikacja automatycznie:
- Utworzy baze SQLite w `/volume2/docker/cennik/data/cennik.db`
- Utworzy konto admin (sprawdz logi)

```bash
# Sprawdz logi
docker logs cennik-stali
```

## 8. Dostep

- Lokalnie: http://synology-ip:8080
- Przez NPM: https://cennik.twoja-domena.pl

## Komendy

```bash
# Restart
docker restart cennik-stali

# Logi
docker logs -f cennik-stali

# Rebuild po aktualizacji
cd /volume2/docker/cennik
docker-compose down
docker-compose up -d --build
```

## Backup

```bash
# Kopia bazy danych
cp /volume2/docker/cennik/data/cennik.db /volume2/backup/cennik_$(date +%Y%m%d).db
```
