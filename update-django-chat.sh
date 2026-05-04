#!/bin/bash

VENV=/home/zyle44/Documents/nemanja/.venv
PROJECT=/home/zyle44/Documents/nemanja/django_chat
SRC=$PROJECT/src
REQUIREMENTS=/home/zyle44/Documents/nemanja/requirements.txt

cd "$PROJECT" || exit 1

git checkout master
git fetch origin

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "********************************************************"
    echo "$(date) - New updates found. Pulling..."
    git pull origin master

    source "$VENV/bin/activate"
    pip install -r "$REQUIREMENTS"
    cd "$SRC"
    python manage.py migrate
    sleep 1
    systemctl restart django-chat.service

    echo "$(date) - Update applied and service restarted."
    echo "$(date) - Service status: $(systemctl is-active django-chat.service)"
    echo "********************************************************"
else
    echo "********************************************************"
    echo "$(date) - No updates."
    echo "$(date) - Service status: $(systemctl is-active django-chat.service)"
    echo "********************************************************"
fi
