from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import VerifiedAdminUserManager


class User(AbstractUser):
    """Custom user stored in Postgres (or SQLite in dev): email uniqueness + profile fields."""

    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True after clicking the signup verification link.',
    )

    REQUIRED_FIELDS = ['email']

    objects = VerifiedAdminUserManager()

    def __str__(self):
        return self.username


class Address(models.Model):
    """Stored shipping addresses for authenticated customers."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
    )
    label = models.CharField(
        max_length=80,
        blank=True,
        help_text='Optional tag like Home / Office.',
    )
    recipient_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    state_province = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=32)
    country = models.CharField(max_length=2, help_text='ISO 3166-1 alpha-2, e.g. US')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Addresses'
        indexes = [
            models.Index(fields=['user', '-created_at'], name='users_adrs_user_crt_dt'),
        ]

    def __str__(self):
        return f'{self.recipient_name} — {self.city}'
