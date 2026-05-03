"""Small helpers reused by serializers and browser views."""

from django.contrib.auth import get_user_model
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from .tokens import account_activation_token

User = get_user_model()


def decode_user_uid(uid_b64: str):
    """Return the user decoded from Django's PasswordReset/Base64 UID or None."""

    try:
        uid_int = force_str(urlsafe_base64_decode(uid_b64))
        return User.objects.get(pk=uid_int)
    except (User.DoesNotExist, TypeError, ValueError, OverflowError):
        return None


def account_activation_token_ok(user, token: str) -> bool:
    return account_activation_token.check_token(user, token)


def activate_user_after_email(user):
    user.is_active = True
    user.email_verified = True
    user.save(update_fields=['is_active', 'email_verified'])
