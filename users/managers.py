from django.contrib.auth.models import UserManager as DjangoUserManager


class VerifiedAdminUserManager(DjangoUserManager):
    """Ensure CLI superusers can obtain JWT-backed admin sessions without friction."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('email_verified', True)
        return super().create_superuser(username, email=email, password=password, **extra_fields)
