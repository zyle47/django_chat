# Setup Instructions

Full guide to deploying this app from scratch on a new Linux machine.
Everything runs in Docker — no Python venv, no systemd service needed.

---

## 1. Prerequisites

Install Docker and git:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git
sudo systemctl enable --now docker
```

Add your user to the docker group (so you never need sudo for docker):

```bash
sudo usermod -aG docker $USER
```

Then **log out and log back in** (or reboot) for the group change to take effect.

---

## 2. Clone the repo

```bash
git clone https://github.com/zyle47/django-chat.git
cd django-chat
```

---

## 3. Create the .env file

```bash
cp .env.example .env
nano .env
```

Fill in:

```
SECRET_KEY=<generate a long random string>
ONION_HOST=<leave blank for now — fill in after tor starts>
DEBUG=False
ADMIN_URL=<your-secret-admin-path>
```

To generate a SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## 4. Tor hidden service keys

Two scenarios — pick one:

### A) New site (fresh onion address)

Leave `tor-data/` empty. Tor generates new keys on first start.
Follow the full flow in **section 13**.

### B) Migrating an existing site (keep same onion address)

Copy your existing `tor-data/` directory into the project root before starting:

```bash
cp -rp /path/to/your/tor-data ./tor-data
```

Then continue to section 5.

---

## 5. Start everything

```bash
docker compose up -d --build
```

This builds both images and starts:
- `django-chat` — Django + Daphne on internal port 8000
- `tor` — Tor hidden service pointing at django-chat

Check they're running:

```bash
docker ps
```

Tor takes 2–10 minutes to connect to the network and publish the hidden service.
Watch for it:

```bash
docker logs -f django_chat-tor-1
```

You're ready when you see: `Bootstrapped 100% (done): Done`
Hidden service is published when you see: `Your Tor onion service descriptor has been published`

---

## 6. Update ONION_HOST in .env

Get your onion address:

```bash
sudo cat tor-data/hostname
```

Put it in `.env` as `ONION_HOST`, then apply it:

```bash
docker compose down && docker compose up -d
```

Note: `restart` alone does not re-read the `.env` file — always use `down && up`.

Verify it loaded:

```bash
docker compose exec django-chat env | grep ONION
```

---

## 7. First-time Django setup

Create a superuser (admin account):

```bash
docker compose exec django-chat python manage.py createsuperuser
```

---

## 8. Set up cron jobs

Open crontab:

```bash
crontab -e
```

Add these three entries:

```
*/5 * * * * /home/<user>/django_chat/update-django-chat.sh >> /home/<user>/django_chat/update_log.txt 2>&1
*/5 * * * * cd /home/<user>/django_chat && docker compose exec -T django-chat python manage.py cleanup_expired_images
*/5 * * * * cd /home/<user>/django_chat && docker compose exec -T django-chat python manage.py cleanup_expired_messages
```

Replace `<user>` with your Linux username and the path with wherever you cloned the repo.

What each cron does:
- **update-django-chat.sh** — checks for new commits on master every 5 min, pulls and restarts django-chat if there are updates (rebuilds image only if requirements.txt changed). Also restarts tor if it becomes unhealthy.
- **cleanup_expired_images** — deletes images older than 12 hours
- **cleanup_expired_messages** — deletes messages older than 24 hours

---

## 9. Auto-start on boot

Docker starts automatically on boot (enabled in step 1). Both containers have `restart: unless-stopped`, so they come back up on their own after a reboot — no commands needed.

---

## 10. Backing up

The only things that matter for a full restore:

| What | Where |
|------|-------|
| Database | `src/db.sqlite3` |
| Uploaded images | `src/media/` |
| Tor onion keys | `tor-data/` |
| Secrets | `.env` |

Everything else can be rebuilt from the git repo.

**Important:** `tor-data/` contains the private key that defines your onion address. Back it up somewhere safe. If you lose it, the onion address is gone forever.

---

## 11. File structure

```
django_chat/
  src/                  Django project (bind-mounted into django-chat container)
  tor/                  Tor container build files
    Dockerfile
    torrc
    entrypoint.sh
  tor-data/             Tor hidden service keys (gitignored — back these up!)
  Dockerfile            Django app image
  docker-compose.yml
  entrypoint.sh         Django container entrypoint (migrate → collectstatic → daphne)
  requirements.txt      Pinned Python dependencies
  update-django-chat.sh Auto-update + tor watchdog script (run by cron)
  .env                  Secrets (gitignored)
  .env.example          Template for .env
```

---

## 12. Useful commands

```bash
# Check container status
docker ps

# Follow all logs
docker compose logs -f

# Follow tor logs only
docker logs -f django_chat-tor-1

# Follow django logs only
docker logs -f django_chat-django-chat-1

# Stop everything
docker compose down

# Start everything
docker compose up -d

# Force re-read of .env
docker compose down && docker compose up -d

# Restart only django (after a manual code change)
docker compose restart django-chat

# Restart tor (if it gets stuck)
docker compose restart tor

# Check what env vars the django container has loaded
docker compose exec django-chat env | grep ONION

# Run a Django management command
docker compose exec django-chat python manage.py <command>

# Run migrations
docker compose exec django-chat python manage.py migrate

# Open Django shell
docker compose exec django-chat python manage.py shell
```

---

## 13. Spinning up a new instance with a fresh onion address

Do this when you want a brand new site with its own onion address — e.g. a second copy on another machine.

**Step 1** — Follow steps 1–3 (prerequisites, clone, .env). Leave `ONION_HOST` blank.

**Step 2** — Make sure `tor-data/` is empty. If it has files, clear them (the directory is owned by tor's UID so use find):

```bash
sudo find tor-data/ -mindepth 1 -delete
```

**Step 3** — Start the containers:

```bash
docker compose up -d --build
```

**Step 4** — Wait for tor to bootstrap:

```bash
docker logs -f django_chat-tor-1
```

Wait until you see `Bootstrapped 100% (done): Done`.

**Step 5** — Get your new onion address. Tor writes keys directly into `tor-data/` via the bind mount:

```bash
sudo cat tor-data/hostname
```

**Step 6** — Put the onion address into `.env` and apply it:

```bash
nano .env  # set ONION_HOST=<your new .onion address>
docker compose down && docker compose up -d
```

Verify:

```bash
docker compose exec django-chat env | grep ONION
```

**Step 7** — Create a superuser and set up cron jobs (steps 7 and 8 of the main guide).

That's it. Your new instance is live on its own unique onion address.

---

## Notes

- **Never commit** `tor-data/`, `.env`, `src/db.sqlite3`, or `src/media/` — all gitignored
- The site is only accessible via the onion address — `127.0.0.1:8000` is not exposed to the host
- Tor health is checked every 60 seconds via the control port; the cron watchdog restarts it if unhealthy
- `restart` alone does not re-read `.env` — always use `docker compose down && docker compose up -d`
- Django runs with Daphne (ASGI), not `runserver`
