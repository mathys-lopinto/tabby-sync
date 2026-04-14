#!/bin/sh
set -e
cd /app
/venv/bin/python ./manage.py migrate
exec /venv/bin/gunicorn
