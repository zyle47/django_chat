#!/bin/sh
set -e
chown -R tor:tor /var/lib/tor/django_chat
chmod 700 /var/lib/tor/django_chat
exec tor -f /etc/tor/torrc
