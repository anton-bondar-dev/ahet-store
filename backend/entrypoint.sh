#!/bin/sh
# Startup for the web container: apply DB migrations and collect static files,
# then hand off to whatever CMD was given (gunicorn in production).
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# exec so gunicorn becomes PID 1 and receives Docker's stop signals directly.
exec "$@"
