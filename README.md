# Ahet Store

A full-stack e-commerce platform with a built-in support helpdesk, built end to
end — storefront, checkout, and the internal tooling a team needs to run it.

**Live demo:** https://django-ecommerce.overpro.fit

Sign in with one click on the login page — three roles, no registration needed:

| Role | What it shows |
| --- | --- |
| Покупець (customer) | catalog, cart, checkout, order history, bonuses, support chat |
| Оператор (operator) | ticket queue, canned-reply macros, customer tags, impersonation |
| Власник (owner) | everything above, plus analytics, the approval queue, and the audit log |

Password for all demo accounts: `demo2026`.

---

## Features

**Storefront**
- Nested category tree with live counts, search with suggestions, price filter
- Product pages with an image gallery, reviews and threaded replies
- Wishlist, and a cart that merges correctly when a guest signs in
- Discounts, stock tracking, and a bonus-points loyalty program
- Checkout with server-side stock locking (no overselling)

**Authentication**
- Email/password, Google OAuth, and password reset
- Two-factor authentication via a Telegram bot (tap-to-approve with a match code)
- A per-user security stamp so "log out everywhere" invalidates every token instantly

**Support helpdesk (staff)**
- Ticket queue with SLA tracking (overdue tickets surface automatically)
- Canned-reply macros with placeholders, customer tags, agent presence
- "View as customer" impersonation (read-only, revocable) for debugging issues
- An approval flow for high-value actions and a full admin audit log
- Role-based access: operators vs. owner (audit log and approvals are owner-only)

**Analytics dashboard**
- Revenue, top sellers, average order value, and low-stock warnings
- Support metrics: open/closed tickets, SLA breaches, satisfaction rate

---

## Tech stack

**Backend** — Python 3.12, Django 5, Django Ninja, PostgreSQL, JWT auth. Runs in
Docker behind nginx and gunicorn.

**Frontend** — React 19, TypeScript, Vite, TanStack Query, Tailwind CSS.

**Contract-first API.** The frontend's API client is generated from the backend's
OpenAPI schema, so the two can never silently drift apart — a backend change that
would break the frontend fails the build instead of failing in production:

```
Django Ninja  ->  backend/openapi.json  ->  Orval  ->  frontend/src/api/generated/  (typed React Query hooks)
```

---

## Project structure

```
backend/          Django project
  apps/
    accounts/     auth, JWT, 2FA (Telegram/email), Google OAuth, profiles
    catalog/      products, categories, search
    cart/         cart + guest→user merge
    orders/       checkout, stock locking, bonuses
    reviews/      product reviews and replies
    support/      helpdesk: tickets, macros, tags, impersonation, audit log
    analytics/    owner dashboard metrics
    wishlist/     wishlist
    core/         API router, shared permissions
frontend/         React + Vite app
  src/
    api/generated/  Orval-generated typed client (do not edit by hand)
    pages/  components/  hooks/  context/  lib/
```

## Local development

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in the values
python manage.py migrate
python manage.py runserver
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

When the backend's API changes, regenerate the typed client:

```bash
cd frontend
npm run api:generate
```

## Deployment

The backend ships as a Docker image (`docker compose up -d --build`) behind nginx,
which also serves the built frontend (`npm run build`) and the media/static files.
