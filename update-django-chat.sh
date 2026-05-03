#!/bin/bash

# Go to project directory
cd /home/zyle44/Documents/nemanja/django_chat || exit 1

# Ensure we are on master
git checkout master

# Fetch latest commits from origin
git fetch origin

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "********************************************************"
    echo "$(date) - New updates found. Pulling..."
    git pull origin master

    # Activate virtual environment
    source venv/bin/activate

    # Install new dependencies if any
    pip install -r requirements.txt

    # Apply Django migrations
    python manage.py migrate
    sleep(1)
    # Restart Django service
    systemctl restart django-chat.service

    echo "$(date) - Update applied and service restarted."
    echo "$(date) - Service status: $(systemctl is-active django-chat.service)" | tee -a $LOG_FILE
    echo "********************************************************"
else
    echo "********************************************************"
    echo "$(date) - No updates."
    echo "$(date) - Service status: $(systemctl is-active django-chat.service)" | tee -a $LOG_FILE
    echo "********************************************************"
fi
