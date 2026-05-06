#!/bin/bash

PROJECT=/home/zyle44/Documents/nemanja/django_chat

cd "$PROJECT" || exit 1

# Tor watchdog — restart if unhealthy
TOR_HEALTH=$(docker compose ps --format '{{.Health}}' tor 2>/dev/null || echo "")
if [ "$TOR_HEALTH" = "unhealthy" ]; then
    echo "$(date) - Tor is unhealthy. Restarting..."
    docker compose restart tor
fi

git checkout master
git fetch origin

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "********************************************************"
    echo "$(date) - New updates found. Pulling..."

    OLD_REQS=$(git show HEAD:requirements.txt 2>/dev/null || echo "")
    git pull origin master
    NEW_REQS=$(cat requirements.txt)

    if [ "$OLD_REQS" != "$NEW_REQS" ]; then
        echo "$(date) - Requirements changed. Rebuilding image..."
        docker compose build
    fi

    docker compose up -d django-chat

    echo "$(date) - Update applied."
    echo "$(date) - Container status: $(docker compose ps --format '{{.State}}' django-chat 2>/dev/null || echo unknown)"
    echo "********************************************************"
else
    echo "********************************************************"
    echo "$(date) - No updates."
    echo "$(date) - Container status: $(docker compose ps --format '{{.State}}' django-chat 2>/dev/null || echo unknown)"
    echo "********************************************************"
fi
