"""Accounts-test-local fixtures.

Keep the suite deterministic and fully offline by neutralising the two
fire-and-forget side effects the auth endpoints trigger:

  * `send_login_prompt` — a real Telegram Bot API HTTP call (the token is set in
    the dev .env, so without this the login-with-Telegram path hits the network);
  * `send_login_alert_async` / `send_password_reset_async` — background e-mail
    threads whose timing would otherwise race the assertions.

The synchronous `send_email_otp` path is intentionally left untouched so the
e-mail OTP still lands in Django's locmem outbox and can be asserted on.
"""
import pytest


@pytest.fixture(autouse=True)
def _no_external_side_effects(monkeypatch):
    import apps.accounts.api as api_mod

    monkeypatch.setattr(api_mod, "send_login_prompt", lambda *a, **k: None)
    monkeypatch.setattr(api_mod, "send_login_alert_async", lambda *a, **k: None)
    monkeypatch.setattr(api_mod, "send_password_reset_async", lambda *a, **k: None)
