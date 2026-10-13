"""kb-builder runs on one machine for one person: no database, no accounts, no admin."""

from pathlib import Path

KB_BUILDER_VERSION: str = "0.2.1"  # bump on every release; start.py compares it with GitHub

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR / "project"

# Only reachable from this computer (manage.py review binds to 127.0.0.1), so a fixed key is fine.
SECRET_KEY = "kb-builder-local-only"
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = ["kb"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]
DATABASES = {}
USE_TZ = True
TIME_ZONE = "Europe/Amsterdam"
