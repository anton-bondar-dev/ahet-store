"""Shared pytest fixtures for the whole backend test suite.

Conventions used across all app tests:
  * `api`              — a Django test Client; the API is mounted at /api/...
  * `bearer(user)`     — auth headers (a stamped JWT + a session id) for that user
  * `make_user(...)`   — create a customer / staff / owner
  * `category_factory` / `product_factory` — minimal valid catalog objects
  * `post_json` / `put_json` — JSON request helpers
"""
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def api():
    return Client()


@pytest.fixture
def bearer(db):
    """Auth headers carrying a valid, security-stamped access token."""
    from apps.accounts.models import Profile
    from ninja_jwt.tokens import RefreshToken

    def _headers(user, session_id="test-session"):
        profile, _ = Profile.objects.get_or_create(user=user)
        access = RefreshToken.for_user(user).access_token
        access["stamp"] = str(profile.security_stamp)
        return {"Authorization": f"Bearer {access}", "X-Session-Id": session_id}

    return _headers


@pytest.fixture
def make_user(db):
    def _make(username="user", password="pw", email=None, is_staff=False, is_superuser=False):
        email = email if email is not None else f"{username}@example.com"
        return User.objects.create_user(
            username=username, email=email, password=password,
            is_staff=is_staff, is_superuser=is_superuser,
        )

    return _make


@pytest.fixture
def category_factory(db):
    from apps.catalog.models import Category

    counter = {"n": 0}

    def _make(name=None, **kwargs):
        counter["n"] += 1
        name = name or f"Category {counter['n']}"
        return Category.objects.create(name=name, slug=f"cat-{counter['n']}", **kwargs)

    return _make


@pytest.fixture
def product_factory(db, category_factory):
    from apps.catalog.models import Product

    counter = {"n": 0}

    def _make(category=None, price="100.00", stock=10, **kwargs):
        counter["n"] += 1
        category = category if category is not None else category_factory()
        return Product.objects.create(
            category=category, title=f"Product {counter['n']}",
            slug=f"prod-{counter['n']}", price=price, stock=stock, **kwargs,
        )

    return _make


@pytest.fixture
def post_json(api):
    def _post(path, data, headers=None):
        return api.post(path, data=json.dumps(data),
                        content_type="application/json", headers=headers or {})
    return _post


@pytest.fixture
def put_json(api):
    def _put(path, data, headers=None):
        return api.put(path, data=json.dumps(data),
                       content_type="application/json", headers=headers or {})
    return _put
