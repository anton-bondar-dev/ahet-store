"""Settings for the test suite: a throwaway sqlite database, fast password
hashing, and an in-memory e-mail backend so tests need no Postgres, no network
and no real secrets."""
import os

# Must be set before config.settings is imported (load_dotenv there won't
# override an already-set variable), so the prod fail-closed checks stay off.
os.environ.setdefault("DEBUG", "True")

from .settings import *  # noqa: F401,F403,E402

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
