#!/bin/bash
set -e

export DJANGO_SETTINGS_MODULE=djchat.settings

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

exec daphne -b 0.0.0.0 -p 8000 djchat.asgi:application
