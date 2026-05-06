# DJ Chat Project

Simple room-based chat app built with Django + Channels.

## Features

- Lobby page to create/join rooms
- Live lobby room list updates (no refresh needed)
- Real-time room chat over WebSockets
- Stable per-room message colors per user
- Room-level passwords (required on room creation, required on join)
- Room soft delete/restore controls for superadmin
- Message persistence to SQLite
- User authentication (signup/login/logout)
- Superadmin approval workflow for new registrations
- Django admin support for rooms/messages
- Basic model and view tests

## Setup

From the project root:

```powershell
C:\Users\Nemanja PC\AppData\Local\Programs\Python\Python314\python.exe -m venv .venv
.venv\Scripts\python.exe -m ensurepip --upgrade --default-pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run migrations

```powershell
cd src
..\.venv\Scripts\python.exe manage.py migrate
```

## Run the server

```powershell
cd src
..\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`.

You should see `Starting ASGI/Daphne ...` in terminal output. If you don't,
you are not using the correct environment/dependencies.

## Authentication flow

- Create account at `/signup/`
- New accounts are created with `is_active=False` and must be approved by a superadmin
- Pending users are redirected to `/signup/pending/`
- Login at `/accounts/login/` works only for approved (`is_active=True`) users
- Enter rooms from lobby via `/rooms/enter/` with room name + password
- Rooms at `/chat/<room>/` require authentication
- Superadmin approval page: `/control/users/` (search by username or id, sort, approve/disable)
- Superadmin room control page: `/control/rooms/` (search by room name or id, sort, soft delete/restore)

## Run tests

```powershell
cd src
..\.venv\Scripts\python.exe manage.py test
```

## Admin

Create a superuser:

```powershell
cd src
..\.venv\Scripts\python.exe manage.py createsuperuser
```
6vn7felaig4gmcf5fex6pdjw56zd3hrzpocaoeuk5oewckvjxs7n5eyd.onion

Then open `http://127.0.0.1:8000/admin/`.
