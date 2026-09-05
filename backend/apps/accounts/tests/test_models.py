"""Unit tests for the accounts models: Profile helpers/constraints and the
short-lived login/link token models."""
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import (
    LoginChallenge,
    Profile,
    TelegramLinkToken,
    generate_support_id,
    _SUPPORT_ID_ALPHABET,
)


@pytest.mark.django_db
def test_generate_support_id_shape():
    sid = generate_support_id()
    assert sid.startswith("USR-")
    body = sid[len("USR-"):]
    assert len(body) == 4
    assert all(ch in _SUPPORT_ID_ALPHABET for ch in body)
    # The unambiguous alphabet must exclude the confusable 0/O/1/I.
    assert not (set("01OI") & set(_SUPPORT_ID_ALPHABET))


@pytest.mark.django_db
def test_profile_save_autogenerates_unique_support_id(make_user):
    p1 = Profile.objects.create(user=make_user("a"))
    p2 = Profile.objects.create(user=make_user("b"))
    assert p1.support_id and p1.support_id.startswith("USR-")
    assert p2.support_id and p2.support_id.startswith("USR-")
    assert p1.support_id != p2.support_id


@pytest.mark.django_db
def test_profile_save_keeps_preset_support_id(make_user):
    p = Profile.objects.create(user=make_user("c"), support_id="USR-KEEP")
    assert p.support_id == "USR-KEEP"
    p.city = "Kyiv"
    p.save()
    p.refresh_from_db()
    assert p.support_id == "USR-KEEP"


@pytest.mark.django_db
def test_security_stamp_default_is_uuid(make_user):
    p = Profile.objects.create(user=make_user("d"))
    assert isinstance(p.security_stamp, uuid.UUID)


@pytest.mark.django_db
def test_is_blocked_permanent(make_user):
    p = Profile.objects.create(user=make_user("e"), blocked_permanent=True)
    assert p.is_blocked is True


@pytest.mark.django_db
def test_is_blocked_temporary_future(make_user):
    p = Profile.objects.create(
        user=make_user("f"), blocked_until=timezone.now() + timedelta(hours=1)
    )
    assert p.is_blocked is True


@pytest.mark.django_db
def test_is_blocked_temporary_expired(make_user):
    p = Profile.objects.create(
        user=make_user("g"), blocked_until=timezone.now() - timedelta(hours=1)
    )
    assert p.is_blocked is False


@pytest.mark.django_db
def test_is_blocked_default_false(make_user):
    p = Profile.objects.create(user=make_user("h"))
    assert p.is_blocked is False


@pytest.mark.django_db
def test_profile_defaults(make_user):
    p = Profile.objects.create(user=make_user("i"))
    assert p.preferred_2fa_method == Profile.METHOD_NONE
    assert p.is_2fa_enabled is False
    assert p.bonus_balance == 0
    assert p.operator_status == Profile.STATUS_ONLINE
    assert p.telegram_chat_id is None


@pytest.mark.django_db
def test_profile_str(make_user):
    p = Profile.objects.create(user=make_user("strname"))
    assert str(p) == "Profile<strname>"


@pytest.mark.django_db
def test_telegram_link_token_str_and_defaults(make_user):
    user = make_user("tguser")
    tok = TelegramLinkToken.objects.create(
        user=user, expires_at=timezone.now() + timedelta(minutes=30)
    )
    assert isinstance(tok.token, uuid.UUID)
    assert tok.used_at is None
    assert str(tok) == "LinkToken<tguser>"


@pytest.mark.django_db
def test_login_challenge_str_and_defaults(make_user):
    user = make_user("lcuser")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_EMAIL,
        code="123456",
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    assert ch.status == LoginChallenge.STATUS_PENDING
    assert ch.attempts == 0
    assert isinstance(ch.challenge_id, uuid.UUID)
    assert str(ch) == "Challenge<lcuser:email:pending>"
