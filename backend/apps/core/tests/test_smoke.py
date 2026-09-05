import pytest


@pytest.mark.django_db
def test_database_and_health():
    from django.contrib.auth.models import User
    from django.test import Client

    User.objects.create_user("smoke", "smoke@example.com", "pw")
    assert User.objects.filter(username="smoke").exists()

    resp = Client().get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
