"""Account models for AgencityStudio."""

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils import timezone as django_timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Create users whose stable login identifier is their email address."""

    use_in_migrations = True

    @staticmethod
    def normalize_studio_email(email: str) -> str:
        return BaseUserManager.normalize_email(email).strip().lower()

    def get_by_natural_key(self, email: str):
        return self.get(email__iexact=self.normalize_studio_email(email))

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("The email address is required.")
        email = self.normalize_studio_email(email)
        with transaction.atomic(using=self._db):
            user = self.model(email=email, **extra_fields)
            user.set_password(password)
            user.save(using=self._db)
            from workspaces.services import ensure_personal_workspace

            ensure_personal_workspace(user)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Minimal Studio identity model with email as the login identifier."""

    class Theme(models.TextChoices):
        SYSTEM = "system", _("System")
        LIGHT = "light", _("Light")
        DARK = "dark", _("Dark")

    class Locale(models.TextChoices):
        ENGLISH = "en", _("English")
        FRENCH = "fr", _("French")

    email = models.EmailField(_("email address"), unique=True)
    display_name = models.CharField(_("display name"), max_length=150, blank=True)
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into Django Admin."),
    )
    is_active = models.BooleanField(_("active"), default=True)
    date_joined = models.DateTimeField(_("date joined"), default=django_timezone.now)
    locale = models.CharField(max_length=8, choices=Locale.choices, default=Locale.ENGLISH)
    timezone = models.CharField(max_length=64, default="UTC")
    theme = models.CharField(max_length=12, choices=Theme.choices, default=Theme.SYSTEM)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]
        ordering = ["email"]

    def clean(self):
        super().clean()
        self.email = UserManager.normalize_studio_email(self.email)

    def get_full_name(self) -> str:
        return self.display_name or self.email

    def get_short_name(self) -> str:
        return self.display_name or self.email.split("@", maxsplit=1)[0]

    def __str__(self) -> str:
        return self.get_full_name()
