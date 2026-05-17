# Production deployment — zupperik.dev

Один файл от голого VDS Ubuntu 24.04 LTS до работающего Telegram Mini App на `https://zupperik.dev` и админ-консоли на `https://admin.zupperik.dev`. Идёшь сверху вниз, выполняешь команды по порядку. Все команды на VDS, если не сказано иначе. Где нужно подставить значение — `<...>`.

## 0. Что должно быть готово ДО начала

- [ ] VDS Ubuntu 24.04 LTS, root-доступ по SSH, публичный IPv4 (запиши: `<VDS_IP>`)
- [ ] DNS на name.com:
  - [ ] `zupperik.dev` A-запись → `<VDS_IP>`
  - [ ] `www.zupperik.dev` A-запись → `<VDS_IP>`
  - [ ] `admin.zupperik.dev` A-запись → `<VDS_IP>` *(если хочешь сразу админ-консоль; иначе можно пропустить и добавить позже)*
- [ ] Тестовый Telegram-бот через `@BotFather` → получен `TG_BOT_TOKEN`
- [ ] Зарегистрировано приложение на `https://my.telegram.org/apps` под userbot-аккаунтом → `TG_API_ID` + `TG_API_HASH`
- [ ] Отдельный Telegram-аккаунт (с номером телефона) для userbot — НЕ основной
- [ ] TOTP-приложение на телефоне (Google Authenticator / Aegis / 1Password)
- [ ] Email для уведомлений Let's Encrypt: `mr.niki234@mail.ru`

Проверка DNS перед стартом (с твоего ноута):
```bash
nslookup zupperik.dev
nslookup admin.zupperik.dev
```
Должны вернуть `<VDS_IP>`. Если ответ старый — подожди до 30 минут, name.com распространяет записи быстро, но кеш у DNS-резолверов разный.

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
git clone https://github.com/supperik/telegram-feed.git /opt/telegram-feed
cd /opt/telegram-feed
```

Все дальнейшие команды — из `/opt/telegram-feed`.

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

`API_CORS_ORIGINS` оставь по умолчанию (`https://web.telegram.org,https://zupperik.dev,https://admin.zupperik.dev`). Если решил **не делать** admin-поддомен сейчас, убери из строки `,https://admin.zupperik.dev` — потом добавишь.

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
VITE_API_BASE_URL=https://zupperik.dev/api npm run build
```

`VITE_API_BASE_URL` критичен — он зашивается в JS-бандл админки. С ним admin SPA на `admin.zupperik.dev` ходит к API на `zupperik.dev` (cross-origin, CORS уже разрешён в `.env`).

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
  -m mr.niki234@mail.ru \
  -d zupperik.dev -d www.zupperik.dev -d admin.zupperik.dev
```

Если **admin.zupperik.dev пока без A-записи**, убери `-d admin.zupperik.dev` — выпустишь только на два имени:
```bash
sudo certbot certonly --standalone \
  --non-interactive --agree-tos \
  -m mr.niki234@mail.ru \
  -d zupperik.dev -d www.zupperik.dev
```

Сертификаты появятся в `/etc/letsencrypt/live/zupperik.dev/{fullchain.pem,privkey.pem}`. Эта папка будет смонтирована в nginx-контейнер read-only.

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
curl -sk https://zupperik.dev/internal/health           # nginx-ok
curl -sk https://zupperik.dev/api/internal/health       # {"status":"ok",...}
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
curl -s -X POST https://zupperik.dev/api/admin/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"totp\":\"$CODE\"}"
```

Должна вернуться пара `{"access_token":"...","refresh_token":"..."}`.

---

## 10. Настройка BotFather

Открой `@BotFather` в Telegram. Для твоего бота:

1. `/mybots` → выбери бота → **Bot Settings**
2. **Configure Mini App** → **Edit Mini App URL** → введи `https://zupperik.dev`
3. **Bot Settings** → **Domain** → введи `zupperik.dev`
4. **Bot Settings** → **Menu Button** → **Configure menu button** → текст "Open Feed", URL `https://zupperik.dev`

Сохрани изменения. Telegram кеширует Mini App агрессивно — если что-то не работает, удали и пересоздай TMA в BotFather.

---

## 11. Smoke-проверка end-to-end

Получи JWT за пользователя через TMA: открой бота в Telegram → нажми Menu Button → должна загрузиться лента (пока пустая).

Альтернатива — через curl, с фейковым initData *(работает только если backend в режиме `ENV=local`; на проде initData проверяется по HMAC, фальшивый не пройдёт)*. Полноценная проверка — открыть TMA в реальном Telegram-клиенте.

Что должно работать в TMA:
- ✅ Открывается на `zupperik.dev`
- ✅ После загрузки видишь экран с пустой лентой и нижней панелью навигации
- ✅ Вкладка **Sources** → ввести `meduzaproject` → нажать Add → появится индикатор "joining...", через 30-60 секунд статус сменится на "done"
- ✅ Вкладка **Feed** → должны появиться 50 последних постов канала
- ✅ Кнопка Save / Hide на посте — работает оптимистично
- ✅ Тап на пост открывает оригинал в Telegram (`tg://resolve`)

Что должно работать в admin:
- ✅ `https://admin.zupperik.dev` открывает форму логина
- ✅ Логин с email/пароль/TOTP → перенаправляет на `/channels`
- ✅ Список каналов содержит добавленный выше канал → нажать Ban → канал помечается banned, появляется запись в Audit log

CLI-проверка ingester:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 50 ingester
```
Должны быть события `live.new_message`, `live.post_inserted`, `photo.uploaded`.

---

## 12. Maintenance — частые команды

Все команды из `/opt/telegram-feed`. Создай alias, чтобы не повторять `-f` каждый раз:
```bash
echo "alias dcp='docker compose -f docker-compose.yml -f docker-compose.prod.yml'" >> ~/.bashrc
source ~/.bashrc
```

**Логи:**
```bash
dcp logs -f --tail=100              # все сервисы
dcp logs -f ingester                # один сервис
```

**Перезапуск после изменения .env:**
```bash
dcp restart api ingester
```

**Pull нового кода + редеплой:**
```bash
cd /opt/telegram-feed
git pull

# Если поменялся backend
dcp build api ingester
dcp up -d api ingester
dcp exec api alembic upgrade head

# Если поменялся TMA
cd frontend/tma && npm ci && npm run build && cd ../..
dcp restart nginx

# Если поменялся admin
cd frontend/admin && npm ci && VITE_API_BASE_URL=https://zupperik.dev/api npm run build && cd ../..
dcp restart nginx
```

**Бэкап Postgres (раз в день, cron):**
```bash
dcp exec -T postgres pg_dump -U tgf telegram_feed | gzip > /opt/telegram-feed/backups/$(date +%F).sql.gz
```

Простой cron:
```bash
mkdir -p /opt/telegram-feed/backups
(crontab -l 2>/dev/null; echo "0 4 * * * cd /opt/telegram-feed && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres pg_dump -U tgf telegram_feed | gzip > /opt/telegram-feed/backups/\$(date +\%F).sql.gz") | crontab -
```

**Полная остановка:**
```bash
dcp down            # без потери данных
dcp down -v         # ⚠ удалит volumes (Postgres data, MinIO, tg_session) — НЕ запускай если не знаешь зачем
```

---

## 13. Troubleshooting

### `curl https://zupperik.dev/...` → SSL handshake error
- Сертификат не выпустился: `sudo certbot certificates` — должна быть строка `zupperik.dev`.
- nginx не подхватил: `dcp restart nginx && dcp logs nginx`.
- ufw закрыл 443: `sudo ufw status`.

### Mini App в Telegram показывает белый экран
- Открой URL в браузере: `https://zupperik.dev`. Если 404 — TMA dist не собран или не смонтирован.
- Проверь: `ls /opt/telegram-feed/frontend/tma/dist/index.html`.
- В nginx: `dcp exec nginx ls /var/www/tma`.

### Mini App не открывается в Telegram (но в браузере работает)
- В BotFather Domain не выставлен. Bot Settings → Domain → `zupperik.dev`.
- Mini App URL не выставлен или кеш Telegram старый. Пересоздай Mini App в BotFather.

### Ingester не подключается, в логах FloodWaitError
- Аккаунт уже зашёл с другого IP / устройства недавно. Подожди указанное в ошибке количество секунд.
- Не используй основной Telegram-аккаунт как userbot.

### Ingester циклится с запросом кода SMS
- Сессия не сохранилась. Запусти интерактивный шаг 8 заново, **дай 10+ секунд** после `ingester.connected` перед Ctrl+C.
- Volume `tg_session` есть? `docker volume ls | grep tg_session`.

### `POST /api/sources` возвращает 202, но канал не появляется
- Проверь логи ingester: `dcp logs ingester | grep join_worker`.
- Username канала: только публичные, формат `meduzaproject` (без `@`).
- Если канал был раньше добавлен и не нашёлся — заведи issue `bd create`, есть баг `telegram-feed-cfm` про регистр username'а.

### Admin SPA загружается, но логин выдаёт CORS-ошибку
- В `.env` нет `https://admin.zupperik.dev` в `API_CORS_ORIGINS`.
- После правки: `dcp restart api`.

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

- [ ] `https://zupperik.dev/internal/health` → `nginx-ok`
- [ ] `https://zupperik.dev/api/internal/health` → `{"status":"ok"}`
- [ ] `https://admin.zupperik.dev/` загружает форму логина
- [ ] `dcp logs ingester` показывает `ingester.connected` без ошибок
- [ ] В Telegram бот открывает TMA, видна лента
- [ ] Добавление канала через TMA → backfill отрабатывает за < 60 секунд
- [ ] Логин в admin → ban канала → запись в Audit log
- [ ] `sudo certbot renew --dry-run` проходит

Если все пункты ✅ — деплой завершён.
