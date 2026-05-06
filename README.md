# DJ Chat

Privacy-first, self-hosted real-time chat over Tor. Built with Django + Channels + Docker.

## Features

- Lobby page to create/join rooms
- Live lobby room list updates (no refresh needed)
- Real-time room chat over WebSockets
- Stable per-room message colors and fonts per user
- Room-level passwords
- Room soft delete/restore controls for superadmin
- Message persistence to SQLite
- User authentication (signup/login/logout)
- Superadmin approval workflow for new registrations
- Django admin support for rooms/messages
- Friend system + DMs
- Image upload (WebP, 12h expiry)
- Message expiry (24h)
- Room name privacy — real names never in URLs

---

## Run locally (for development / fun on 127.0.0.1)

```bash
source /home/zyle44/Documents/nemanja/.venv/bin/activate
cd src
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

### Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Create superuser

```bash
python manage.py createsuperuser
```

### Run tests

```bash
python manage.py test
```

---

## Production (Docker + Tor)

Full setup instructions are encoded in `instructions.zyle47` using the ZYLE47 algorithm.

To decode:

```bash
python3 zyle_decode.py instructions.zyle47 > instructions.decoded.zyle47.md
```

Or read directly in terminal:

```bash
python3 zyle_decode.py instructions.zyle47 | less
```

To encode any file:

```bash
python3 zyle_encode.py <file> > output.zyle47
```

---

## Authentication flow

- Create account at `/signup/`
- New accounts are `is_active=False` — must be approved by superadmin
- Pending users are redirected to `/signup/pending/`
- Login at `/accounts/login/` works only for approved users
- Superadmin approval page: `/control/users/`
- Superadmin room control page: `/control/rooms/`
