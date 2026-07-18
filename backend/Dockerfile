# syntax=docker/dockerfile:1
# Production image for the Ahet Store Django backend.
FROM python:3.12-slim

# - PYTHONDONTWRITEBYTECODE: no .pyc files in the container
# - PYTHONUNBUFFERED: stream logs straight to the container stdout (docker logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
# psycopg-binary and Pillow ship manylinux wheels, so no build toolchain needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project code (see .dockerignore for what stays out).
COPY . .

# migrate + collectstatic run at startup, then gunicorn takes over.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
