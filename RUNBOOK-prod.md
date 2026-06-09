# Production deployment

Один файл от голого VDS Ubuntu 24.04 LTS до работающего Telegram Mini App на `https://<DOMAIN>` и админ-консоли на `https://admin.<DOMAIN>`. Идёшь сверху вниз, выполняешь команды по порядку. Все команды на VDS, если не сказано иначе. Где нужно подставить значение — `<...>`.

**Плейсхолдеры, которые встречаются в этом runbook'е** (выпиши свои значения и подставляй по ходу):

| Плейсхолдер | Что это |
| --- | --- |
| `<DOMAIN>` | основной домен под TMA, например `example.com` |
| `admin.<DOMAIN>` | поддомен под админ-консоль |
| `<VDS_IP>` | публичный IPv4 VDS |
| `<LETSENCRYPT_EMAIL>` | email для уведомлений Let's Encrypt о приближающейся expiry |
| `<REPO_URL>` | https-URL git-репозитория с этим проектом (например `https://github.com/<owner>/telegram-feed.git`) |

## 0. Что должно быть готово ДО начала

- [ ] VDS Ubuntu 24.04 LTS, root-доступ по SSH, публичный IPv4 (запиши: `<VDS_IP>`)
- [ ] DNS у твоего регистратора:
  - [ ] `<DOMAIN>` A-запись → `<VDS_IP>`
  - [ ] `www.<DOMAIN>` A-запись → `<VDS_IP>`
  - [ ] `admin.<DOMAIN>` A-запись → `<VDS_IP>` *(если хочешь сразу админ-консоль; иначе можно пропустить и добавить позже)*
- [ ] Тестовый Telegram-бот через `@BotFather` → получен `TG_BOT_TOKEN`
- [ ] Зарегистрировано приложение на `https://my.telegram.org/apps` под userbot-аккаунтом → `TG_API_ID` + `TG_API_HASH`
- [ ] Отдельный Telegram-аккаунт (с номером телефона) для userbot — НЕ основной
- [ ] TOTP-приложение на телефоне (Google Authenticator / Aegis / 1Password)
- [ ] Email для уведомлений Let's Encrypt: `<LETSENCRYPT_EMAIL>`

Проверка DNS перед стартом (с твоего ноута):
```bash
nslookup <DOMAIN>
nslookup admin.<DOMAIN>
```
Должны вернуть `<VDS_IP>`. Если ответ старый — подожди до 30 минут; разные регистраторы распространяют записи с разной скоростью, плюс у DNS-резолверов свой кеш.

---

## 1. Подключение к VDS и базовая безопасность

```bash
ssh root@<VDS_IP>
```

Системное обновление + базовый софт:
```bash
apt update && apt upgrade -y
apt install -y git curl ufw fail2ban ca-certificates
```

Файрвол (открываем только нужное):
```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status
```

Должно быть видно три правила: `22/tcp ALLOW`, `80/tcp ALLOW`, `443/tcp ALLOW`.

Создай пользователя для деплоя (не работаем под root):
```bash
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

Переключайся под него:
```bash
exit
ssh deploy@<VDS_IP>
```

---

## 2. Docker, Node.js, certbot

Docker Engine + Compose plugin (одной командой, официальный installer):
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Перелогинься, чтобы группа подтянулась:
```bash
exit
ssh deploy@<VDS_IP>
docker --version          # Docker version 27.x.x
docker compose version    # Docker Compose version v2.30.x
```

Node.js 20 LTS (нужен только для сборки фронтов):
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version    # v20.x
npm --version
```

Certbot (для Let's Encrypt):
```bash
sudo apt install -y certbot
```

---

## 3. Клонирование репозитория

```bash
sudo mkdir -p /opt/telegram-feed
sudo chown deploy:deploy /opt/telegram-feed
git clone <REPO_URL> /opt/telegram-feed
cd /opt/telegram-feed
```

Все дальнейшие команды — из `/opt/telegram-feed`.

**Sanity-check владельца** (важно — типичная грабля: если `git clone` был выполнен не из-под `deploy`, файлы окажутся `root:root`, и поздняя auto-deploy через ssh+`deploy` упадёт с `fatal: detected dubious ownership` и `.env: permission denied`):
```bash
stat -c '%U:%G' /opt/telegram-feed/.git/config
# Ожидается: deploy:deploy. Если видишь `root:root` — починить рекурсивно:
sudo chown -R deploy:deploy /opt/telegram-feed
```

---

## 4. Подготовка `.env`

```bash
cp .env.prod.example .env
```

Сгенерируй секреты (выведет три строки — скопируй их в `.env`):
```bash
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
echo "MINIO_ACCESS_KEY=$(openssl rand -hex 8)"
echo "MINIO_SECRET_KEY=$(openssl rand -hex 32)"
echo "API_JWT_SECRET=$(openssl rand -hex 32)"
```

Отредактируй `.env`:
```bash
nano .env
```

Замени все `<REPLACE_*>` на сгенерированные значения. Заполни вручную:
- `TG_API_ID` и `TG_API_HASH` — с my.telegram.org/apps
- `TG_PHONE` — номер userbot-аккаунта, формат `+79991234567`
- `TG_BOT_TOKEN` — токен от @BotFather

`API_CORS_ORIGINS` оставь по умолчанию (`https://web.telegram.org,https://<DOMAIN>,https://admin.<DOMAIN>`). Если решил **не делать** admin-поддомен сейчас, убери из строки `,https://admin.<DOMAIN>` — потом добавишь.

**Если VDS-провайдер блокирует исходящий трафик к Telegram MTProto** (типичный симптом — `telethon.network.mtprotosender: Attempt N at connecting failed: TimeoutError` на шаге 8, при этом `curl https://1.1.1.1` отвечает) — пропусти userbot через свой MTProxy:
```
TG_PROXY_TYPE=mtproxy
TG_PROXY_HOST=<твой mtproxy host>
TG_PROXY_PORT=<порт, обычно 443>
TG_PROXY_SECRET=<32-символьный hex secret из @MTProxybot или mtg>
```
Оставь `TG_PROXY_TYPE` пустым (по умолчанию) — Telethon идёт напрямую к Telegram-DC.

**Рекомендуемый путь — naive sidecar (если у тебя есть `naive+https://` аккаунт):**

`docker-compose` поднимает naive-сайдкар — он заворачивает SOCKS5 → NaiveProxy-туннель → твой сервер → Telegram. Конфиг подаётся целиком через `naive+https://` URI: init-контейнер (`naive-init`) парсит его в naive `config.json` до старта sidecar'а. Никакого ручного JSON.

1. В `.env` (вместо `TG_PROXY_TYPE=mtproxy`):
   ```
   TG_PROXY_TYPE=socks5
   TG_PROXY_HOST=naive
   TG_PROXY_PORT=1080
   TG_PROXY_SECRET=
   TG_NAIVE_URL=naive+https://<user>:<pass>@<host>:<port>#<name>
   ```
   Транспорты `https` (HTTP/2) и `quic` (HTTP/3); padding в naive автоматический — отдельных параметров не нужно.

2. Перезапуск (`--build` — образ naive собирается локально из `infra/naive/`):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build naive-init naive
   # --force-recreate: иначе ingester не подхватит новый .env (docker compose restart не перечитывает env_file)
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate ingester
   docker compose -f docker-compose.yml -f docker-compose.prod.yml logs naive-init    # "wrote naive config to /etc/naive/config.json", без ошибок
   docker compose -f docker-compose.yml -f docker-compose.prod.yml logs ingester | tail -30
   ```
   В логах ingester появится `ingester.connected user_id=...`. Если до этого был fresh deploy (или после `down -v`) — сначала повтори шаг 8 (интерактивный SMS-логин).

**Fallback — VLESS sidecar (xray):**

Сервисы `xray-init`/`xray` убраны из активного `docker-compose.yml` (по умолчанию — naive); `infra/xray/parse_vless.py` и `config.example.json` остаются в репо. Чтобы вернуть VLESS — добавь блок обратно в `docker-compose.yml`, верни том `xray_config:` в секцию `volumes:` и поменяй `ingester.depends_on` с `naive` на `xray`:
   ```yaml
     xray-init:
       image: python:3.12-alpine
       restart: "no"
       env_file: .env
       volumes:
         - ./infra/xray/parse_vless.py:/parse_vless.py:ro
         - xray_config:/etc/xray
       command: ["python", "/parse_vless.py"]
     xray:
       image: ghcr.io/xtls/xray-core:25.12.8
       restart: unless-stopped
       depends_on:
         xray-init: { condition: service_completed_successfully }
       volumes:
         - xray_config:/etc/xray:ro
       command: ["run", "-config", "/etc/xray/config.json"]
   ```

Если MTProxy недоступен или капризничает (FakeTLS-варианты иногда не работают с Telethon), подними локальный xray-sidecar — он заворачивает SOCKS5 → VLESS-туннель → твой сервер → Telegram. Это более устойчивый путь: TLS-маскированный трафик сложнее блокировать DPI.

Конфиг подаётся целиком через `vless://` URL — отдельный init-контейнер (`xray-init`) парсит его в xray config.json до старта sidecar'a. Никакого ручного JSON.

1. В `.env` (вместо `TG_PROXY_TYPE=mtproxy`):
   ```
   TG_PROXY_TYPE=socks5
   TG_PROXY_HOST=xray
   TG_PROXY_PORT=1080
   TG_PROXY_SECRET=
   TG_VLESS_URL=vless://<uuid>@<host>:<port>?security=tls&sni=...&type=tcp#<name>
   ```
   Поддерживаемые транспорты: `type=tcp` (с `security=tls` или `security=reality`) и `type=xhttp` (с TLS). Если URL формата другого транспорта (например `type=ws` или `type=grpc`) — расширь `infra/xray/parse_vless.py` или используй fallback (см. ниже).

2. Перезапуск:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d xray-init xray
   docker compose -f docker-compose.yml -f docker-compose.prod.yml restart ingester
   docker compose -f docker-compose.yml -f docker-compose.prod.yml logs xray-init    # должно быть "wrote xray config to /etc/xray/config.json", без ошибок
   docker compose -f docker-compose.yml -f docker-compose.prod.yml logs ingester | tail -30
   ```
   В логах ingester появится `ingester.connected user_id=...`. Если до этого был fresh deploy (или после `docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v`) — сначала повтори шаг 8 (интерактивный SMS-логин).

**Fallback (если transport нестандартный):** в репо лежит шаблон `infra/xray/config.example.json`. Скопируй в `infra/xray/config.json` (gitignored), правь руками, и в `docker-compose.yml` поменяй сервис `xray` обратно на bind-mount `./infra/xray/config.json:/etc/xray/config.json:ro`, убрав сервис `xray-init` и shared volume `xray_config`.

Защити файл:
```bash
chmod 600 .env
```

---

## 5. Сборка фронтов (TMA и admin SPA)

Эти команды собирают статику в `frontend/tma/dist/` и `frontend/admin/dist/`, которую потом nginx раздаст.

**TMA:**
```bash
cd /opt/telegram-feed/frontend/tma
npm ci
npm run build
```

Должна появиться папка `dist/` с `index.html` и `assets/`.

**Admin SPA** *(пропусти, если не делаешь admin-поддомен сейчас)*:
```bash
cd /opt/telegram-feed/frontend/admin
npm ci
VITE_API_BASE_URL=https://<DOMAIN>/api npm run build
```

`VITE_API_BASE_URL` критичен — он зашивается в JS-бандл админки. С ним admin SPA на `admin.<DOMAIN>` ходит к API на `<DOMAIN>` (cross-origin, CORS уже разрешён в `.env`).

Возвращайся в корень:
```bash
cd /opt/telegram-feed
```

---

## 6. SSL-сертификат через Let's Encrypt

Сертификат выпускается до старта nginx-контейнера (certbot занимает порт 80 в standalone-режиме). Открой порт 80 для certbot (в ufw уже открыт) и выпусти:

```bash
sudo certbot certonly --standalone \
  --non-interactive --agree-tos \
  -m <LETSENCRYPT_EMAIL> \
  -d <DOMAIN> -d www.<DOMAIN> -d admin.<DOMAIN>
```

Если **admin.<DOMAIN> пока без A-записи**, убери `-d admin.<DOMAIN>` — выпустишь только на два имени:
```bash
sudo certbot certonly --standalone \
  --non-interactive --agree-tos \
  -m <LETSENCRYPT_EMAIL> \
  -d <DOMAIN> -d www.<DOMAIN>
```

Сертификаты появятся в `/etc/letsencrypt/live/<DOMAIN>/{fullchain.pem,privkey.pem}`. Эта папка будет смонтирована в nginx-контейнер read-only.

**Авто-renewal**: systemd-таймер `certbot.timer` уже запущен после apt install. Проверь:
```bash
sudo systemctl status certbot.timer
```

Хук для перезагрузки nginx после обновления:
```bash
sudo tee /etc/letsencrypt/renewal-hooks/post/reload-nginx.sh > /dev/null <<'EOF'
#!/usr/bin/env bash
cd /opt/telegram-feed
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T nginx nginx -s reload
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/post/reload-nginx.sh
```

Проверь dry-run обновления:
```bash
sudo certbot renew --dry-run
```

---

## 7. Старт стека

Сборка образов:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build api ingester
```

Поднимаем инфру (Postgres / Redis / MinIO):
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis minio
```

Подождать, пока Postgres станет healthy (~5 секунд):
```bash
sleep 8
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Stat `postgres` должен быть `Up ... (healthy)`.

API + миграции:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head
```

Поднимаем nginx (TMA + admin раздаются):
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx
```

Быстрая проверка:
```bash
curl -sk https://<DOMAIN>/internal/health           # nginx-ok
curl -sk https://<DOMAIN>/api/internal/health       # {"status":"ok",...}
```

Если оба ответа правильные — backend + nginx работают.

---

## 8. Первичный логин Telethon (интерактивный SMS)

Userbot подключается к Telegram впервые → ему придёт SMS-код в Telegram (или на телефон, если аккаунт не входит больше нигде). Сессия сохранится в Docker-volume `tg_session`, повторно вводить код **не нужно**.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm -it ingester python -m ingester.main
```

Что произойдёт:
1. Telethon попросит ввести код (5 цифр).
2. Если у аккаунта включена 2FA — попросит пароль (cloud password).
3. После успешного входа в логе появится `ingester.connected user_id=...`.
4. Затем ingester начнёт работу. **Не закрывай сразу** — дай ему 5-10 секунд, чтобы сессия точно сохранилась на диск.
5. Нажми `Ctrl+C` для выхода.

Теперь запусти ingester как фоновый сервис:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d ingester
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 30 ingester
```

В логах должно быть `ingester.connected` без запроса кода. Если просит код снова — значит сессия не сохранилась, повтори шаг.

---

## 9. Создание первого админа

```bash
bash infra/scripts/create_admin.sh
```

Скрипт интерактивно спросит email, пароль (дважды), отрисует QR в терминал. Открой TOTP-приложение → "Scan QR" → отсканируй. Сохрани email/пароль в менеджере паролей **сразу** — без них в админку не зайти, восстановление пока не предусмотрено.

Сразу проверь логин:
```bash
EMAIL=<email>; PASS=<password>; CODE=<6-значный код из TOTP>
curl -s -X POST https://<DOMAIN>/api/admin/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"totp\":\"$CODE\"}"
```

Должна вернуться пара `{"access_token":"...","refresh_token":"..."}`.

---

## 10. Настройка BotFather

Открой `@BotFather` в Telegram. Для твоего бота:

1. `/mybots` → выбери бота → **Bot Settings**
2. **Configure Mini App** → **Edit Mini App URL** → введи `https://<DOMAIN>`
3. **Bot Settings** → **Domain** → введи `<DOMAIN>`
4. **Bot Settings** → **Menu Button** → **Configure menu button** → текст "Open Feed", URL `https://<DOMAIN>`

Сохрани изменения. Telegram кеширует Mini App агрессивно — если что-то не работает, удали и пересоздай TMA в BotFather.

---

## 11. Smoke-проверка end-to-end

Получи JWT за пользователя через TMA: открой бота в Telegram → нажми Menu Button → должна загрузиться лента (пока пустая).

Альтернатива — через curl, с фейковым initData *(работает только если backend в режиме `ENV=local`; на проде initData проверяется по HMAC, фальшивый не пройдёт)*. Полноценная проверка — открыть TMA в реальном Telegram-клиенте.

Что должно работать в TMA:
- ✅ Открывается на `<DOMAIN>`
- ✅ После загрузки видишь экран с пустой лентой и нижней панелью навигации
- ✅ Вкладка **Sources** → ввести `meduzaproject` → нажать Add → появится индикатор "joining...", через 30-60 секунд статус сменится на "done"
- ✅ Вкладка **Feed** → должны появиться 50 последних постов канала
- ✅ Кнопка Save / Hide на посте — работает оптимистично
- ✅ Тап на пост открывает оригинал в Telegram (`tg://resolve`)

Что должно работать в admin:
- ✅ `https://admin.<DOMAIN>` открывает форму логина
- ✅ Логин с email/пароль/TOTP → перенаправляет на `/channels`
- ✅ Список каналов содержит добавленный выше канал → нажать Ban → канал помечается banned, появляется запись в Audit log

CLI-проверка ingester:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 50 ingester
```
Должны быть события `live.new_message`, `live.post_inserted`, `photo.uploaded`.

---

## 12. Maintenance — частые команды

Все команды выполняются из `/opt/telegram-feed`. Compose-команды используют два override-файла, поэтому в этом разделе везде полная форма

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml <subcommand>
```

Если работаешь руками в интерактивной SSH-сессии, можно опционально завести alias в своём `~/.bashrc`:
```bash
echo "alias dcp='docker compose -f docker-compose.yml -f docker-compose.prod.yml'" >> ~/.bashrc
source ~/.bashrc
```
В скриптах и в командах вида `ssh user@host '<cmd>'` этот alias **не работает** — non-interactive shell не загружает `~/.bashrc`, поэтому в этом runbook'е и в `.deploy/DEPLOY.md` дальше всегда подставлена полная команда.

**Логи:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=100              # все сервисы
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f ingester                # один сервис
```

**Перезапуск после изменения .env:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api ingester
```

**Pull нового кода + редеплой:**
```bash
cd /opt/telegram-feed
git pull

# Если поменялся backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml build api ingester
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api ingester
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head

# Если поменялся TMA
cd frontend/tma && npm ci && npm run build && cd ../..
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx

# Если поменялся admin
cd frontend/admin && npm ci && VITE_API_BASE_URL=https://<DOMAIN>/api npm run build && cd ../..
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
```

**Бэкап Postgres (раз в день, cron):**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres pg_dump -U tgf telegram_feed | gzip > /opt/telegram-feed/backups/$(date +%F).sql.gz
```

Простой cron:
```bash
mkdir -p /opt/telegram-feed/backups
(crontab -l 2>/dev/null; echo "0 4 * * * cd /opt/telegram-feed && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres pg_dump -U tgf telegram_feed | gzip > /opt/telegram-feed/backups/\$(date +\%F).sql.gz") | crontab -
```

**Полная остановка:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down            # без потери данных
docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v         # ⚠ удалит volumes (Postgres data, MinIO, tg_session) — НЕ запускай если не знаешь зачем
```

---

## 13. Troubleshooting

### `curl https://<DOMAIN>/...` → SSL handshake error
- Сертификат не выпустился: `sudo certbot certificates` — должна быть строка `<DOMAIN>`.
- nginx не подхватил: `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx && docker compose -f docker-compose.yml -f docker-compose.prod.yml logs nginx`.
- ufw закрыл 443: `sudo ufw status`.

### Mini App в Telegram показывает белый экран
- Открой URL в браузере: `https://<DOMAIN>`. Если 404 — TMA dist не собран или не смонтирован.
- Проверь: `ls /opt/telegram-feed/frontend/tma/dist/index.html`.
- В nginx: `docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx ls /var/www/tma`.

### Mini App не открывается в Telegram (но в браузере работает)
- В BotFather Domain не выставлен. Bot Settings → Domain → `<DOMAIN>`.
- Mini App URL не выставлен или кеш Telegram старый. Пересоздай Mini App в BotFather.

### Ingester не подключается, в логах FloodWaitError
- Аккаунт уже зашёл с другого IP / устройства недавно. Подожди указанное в ошибке количество секунд.
- Не используй основной Telegram-аккаунт как userbot.

### Ingester падает с `Connection to Telegram failed N time(s)` / `TimeoutError` на Attempt 1..6
- VDS-провайдер режет MTProto-IP (`149.154.0.0/16`). Проверь: `curl -v --max-time 6 https://149.154.167.51:443` висит, а `curl https://1.1.1.1` — отвечает.
- Решение: настрой MTProxy через переменные `TG_PROXY_*` в `.env` (см. шаг 4), затем `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart ingester`.
- Решение №1 (рекомендуется): подними **naive-сайдкар** (см. шаг 4 — раздел «Рекомендуемый путь — naive sidecar»). NaiveProxy-туннель маскируется под обычный HTTPS, устойчивее MTProxy к DPI. VLESS (xray) остаётся fallback'ом.
- Альтернатива №2: мигрировать VDS к провайдеру вне зоны блокировки (Hetzner / Contabo / OVH).

### Ingester циклится с запросом кода SMS
- Сессия не сохранилась. Запусти интерактивный шаг 8 заново, **дай 10+ секунд** после `ingester.connected` перед Ctrl+C.
- Volume `tg_session` есть? `docker volume ls | grep tg_session`.

### `POST /api/sources` возвращает 202, но канал не появляется
- Проверь логи ingester: `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs ingester | grep join_worker`.
- Username канала: только публичные, формат `meduzaproject` (без `@`).
- Если канал был раньше добавлен и не нашёлся — заведи issue `bd create`, есть баг `telegram-feed-cfm` про регистр username'а.

### Admin SPA загружается, но логин выдаёт CORS-ошибку
- В `.env` нет `https://admin.<DOMAIN>` в `API_CORS_ORIGINS`.
- После правки: `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api`.

### `certbot renew` падает
- nginx занимает порт 80, certbot не может подняться в standalone. Решение: использовать webroot вместо standalone:
  ```bash
  sudo certbot renew --webroot -w /var/lib/docker/volumes/telegram-feed_certbot_webroot/_data
  ```
  Путь может отличаться — найди через `docker volume inspect telegram-feed_certbot_webroot`.

### Postgres падает по памяти
- VDS на 2 GB RAM впритык. Добавь swap:
  ```bash
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```

---

## 14. Что НЕ покрыто этим runbook'ом

- **Multi-instance / HA** — один VDS, всё на нём.
- **External monitoring** (Sentry, Prometheus) — out of MVP.
- **CI/CD автодеплой** — пока ручной `git pull && build`. Когда понадобится — GitHub Actions с SSH-деплоем.
- **Rate limit на /auth** — open issue `telegram-feed-c8m`, Plan 3 follow-up.
- **Backup-стратегия для MinIO** — фотки можно потерять без бэкапа bucket'а; добавь `mc mirror` к S3 при необходимости.
- **Логи в файлы** — сейчас всё в `docker logs`, ротация по дефолту 10MB×3. Для прода настрой `/etc/docker/daemon.json` с `log-opts max-size`.

---

## 15. Чек-лист "всё работает"

- [ ] `https://<DOMAIN>/internal/health` → `nginx-ok`
- [ ] `https://<DOMAIN>/api/internal/health` → `{"status":"ok"}`
- [ ] `https://admin.<DOMAIN>/` загружает форму логина
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs ingester` показывает `ingester.connected` без ошибок
- [ ] В Telegram бот открывает TMA, видна лента
- [ ] Добавление канала через TMA → backfill отрабатывает за < 60 секунд
- [ ] Логин в admin → ban канала → запись в Audit log
- [ ] `sudo certbot renew --dry-run` проходит

Если все пункты ✅ — деплой завершён.
