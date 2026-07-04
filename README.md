# Online Store

Monorepo for the Online Store project.

## Structure

- **`/backend`** — Python 3.12 + Django 5.x + Django Ninja. Exposes a typed REST API and generates `openapi.json`.
- **`/frontend`** — React + Vite + TypeScript. Consumes the API via [Orval](https://orval.dev/) + [TanStack Query](https://tanstack.com/query) generated from the backend's `openapi.json`.

## API contract flow

```
Django Ninja  ->  backend/openapi.json  ->  Orval  ->  frontend/src/api/generated/ (typed React Query hooks)
```

## Backend — getting started

```bash
cd backend
source .venv/bin/activate
python manage.py runserver
```

## Frontend — getting started

```bash
cd frontend
npm run dev
```
