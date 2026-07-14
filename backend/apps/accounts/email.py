import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger("accounts.email")


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
    try:
        # fail_silently=False so a real SMTP error is caught and logged here
        # (rather than silently swallowed on the background thread).
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
        logger.info("Login alert sent to %s.", email)
    except Exception as exc:  # noqa: BLE001
        logger.error("Login alert FAILED for %s: %s: %s", email, type(exc).__name__, exc)


def send_login_alert_async(email: str, username: str) -> None:
    """Fire-and-forget the login alert. Primitive args (not the ORM object) so
    the worker thread touches no DB connection."""
    # Logged on the request thread (synchronous) so it always shows in the
    # console — proving the login hook fired, independent of the email thread.
    logger.info("LOGIN ALERT: spawning email thread for user '%s' <%s>", username, email)
    threading.Thread(
        target=send_login_alert, args=(email, username), daemon=True
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
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=True,
    )
