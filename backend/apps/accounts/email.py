import logging
import threading

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

logger = logging.getLogger("accounts.email")

# Dummy test domains — never actually sent to (avoids Gmail delivery-failure
# bounces that hurt SMTP reputation).
DUMMY_DOMAINS = ("@example.com", "@test.com")


def _is_dummy(email: str) -> bool:
    return (email or "").lower().endswith(DUMMY_DOMAINS)


def _deliver(subject: str, body: str, recipient: str) -> None:
    """Send one message with a Reply-To (Django adds a Message-ID + Date itself).
    Skips dummy-domain recipients; logs success/failure instead of swallowing."""
    if _is_dummy(recipient):
        logger.info("Skipping real send to dummy recipient %s.", recipient)
        return
    reply_to = [settings.EMAIL_HOST_USER] if settings.EMAIL_HOST_USER else None
    try:
        EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
            reply_to=reply_to,
        ).send(fail_silently=False)
        logger.info("Email sent to %s: %s", recipient, subject)
    except Exception as exc:  # noqa: BLE001
        logger.error("Email FAILED for %s (%s): %s: %s", recipient, subject, type(exc).__name__, exc)


def send_login_alert(email: str, username: str) -> None:
    """Send a 'new login' security alert. Called on a background thread so it
    never delays the HTTP response."""
    if not email:
        logger.warning("Login alert skipped — user '%s' has no email.", username)
        return
    when = timezone.localtime().strftime("%d.%m.%Y о %H:%M")
    subject = "Сповіщення безпеки: Новий вхід в акаунт Ahet Store"
    body = (
        f"Вітаємо, {username}!\n\n"
        f"Щойно було здійснено успішний вхід у ваш акаунт Ahet Store.\n"
        f"Час входу: {when}.\n\n"
        f"Якщо це були ви — можете проігнорувати цей лист.\n"
        f"Якщо ні — негайно змініть пароль та зверніться до підтримки."
    )
    logger.info("Sending login alert to %s …", email)
    _deliver(subject, body, email)


def send_login_alert_async(email: str, username: str) -> None:
    """Fire-and-forget the login alert. Primitive args (not the ORM object) so
    the worker thread touches no DB connection."""
    # Logged on the request thread (synchronous) so it always shows in the
    # console — proving the login hook fired, independent of the email thread.
    logger.info("LOGIN ALERT: spawning email thread for user '%s' <%s>", username, email)
    threading.Thread(
        target=send_login_alert, args=(email, username), daemon=True
    ).start()


def send_password_reset(email: str, name: str, reset_url: str) -> None:
    """Email a password-reset link. With the console backend (dev) the link
    prints to the runserver terminal."""
    subject = "Відновлення пароля Ahet Store"
    body = (
        f"Вітаємо, {name}!\n\n"
        f"Ми отримали запит на відновлення пароля для вашого акаунта Ahet Store.\n"
        f"Щоб встановити новий пароль, перейдіть за посиланням:\n\n{reset_url}\n\n"
        f"Посилання дійсне обмежений час і одноразове.\n"
        f"Якщо ви не робили цей запит — просто проігноруйте цей лист, "
        f"ваш пароль залишиться незмінним."
    )
    # The link carries a valid token — only echo it to the log in DEBUG (dev
    # convenience); never leak it to production logs.
    if settings.DEBUG:
        logger.info("PASSWORD RESET LINK (dev) for %s: %s", email, reset_url)
    else:
        logger.info("Sending password reset link to %s", email)
    _deliver(subject, body, email)


def send_password_reset_async(email: str, name: str, reset_url: str) -> None:
    """Fire-and-forget the reset email so it never delays the response."""
    threading.Thread(
        target=send_password_reset, args=(email, name, reset_url), daemon=True
    ).start()


def send_email_otp(user, code: str) -> None:
    """Email the 6-digit login OTP. With the console backend (dev) the message
    prints to the runserver terminal."""
    subject = "Ваш код входу в Ahet Store"
    body = (
        f"Вітаємо!\n\n"
        f"Ваш код підтвердження для входу в Ahet Store: {code}\n\n"
        f"Код дійсний 2 хвилини. Якщо ви не намагалися увійти, проігноруйте цей лист."
    )
    # Echo the raw code to the log only in DEBUG so it can be grabbed from the
    # terminal in dev; never leak login codes to production logs.
    if settings.DEBUG:
        logger.info("DEVELOPMENT ONLY - OTP CODE: %s", code)
    logger.info("2FA OTP: sending login code to %s", user.email)
    _deliver(subject, body, user.email)
