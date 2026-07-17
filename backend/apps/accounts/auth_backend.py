from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    """Authenticate by email + password instead of username. The `username`
    kwarg carries the email (Django's auth forms pass the identifier there);
    an explicit `email` kwarg is also accepted."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (kwargs.get("email") or username or "").strip()
        if not email or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Shouldn't happen once emails are unique; fail closed if it does.
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
