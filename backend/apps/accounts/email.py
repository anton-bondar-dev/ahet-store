from django.conf import settings
from django.core.mail import send_mail


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
