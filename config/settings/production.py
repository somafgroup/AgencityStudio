"""Production settings for AgencityStudio deployments."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

production_secret = os.getenv("DJANGO_SECRET_KEY", "").strip()
if not production_secret or production_secret == "unsafe-development-key":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a production secret.")
SECRET_KEY = production_secret

production_hosts = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
if not production_hosts:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be configured in production.")
ALLOWED_HOSTS = production_hosts

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    os.getenv("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
)
SECURE_HSTS_PRELOAD = os.getenv("DJANGO_SECURE_HSTS_PRELOAD", "false").lower() == "true"
