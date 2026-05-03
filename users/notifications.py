"""
Email helpers for transactional messages (verification + password flows).
Keeps Django's mail backends (console locally, SMTP when configured).
"""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def _origin(request) -> str:
    fallback = getattr(settings, 'PUBLIC_SITE_ORIGIN', '') or 'http://127.0.0.1'
    fallback = fallback.rstrip('/')

    if request is not None:
        scheme = request.headers.get('X-Forwarded-Proto') or getattr(
            request, 'scheme', 'http'
        )
        host = request.get_host()
        return f'{scheme}://{host}'.rstrip('/')

    return fallback


def send_verification_email(user, *, request=None, token: str) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse('accounts_verify_email', kwargs={'uidb64': uid, 'token': token})
    link = f'{_origin(request)}{path}'

    subject = 'Confirm your email address'
    body = render_to_string(
        'users/emails/verify_email.txt',
        {'user': user, 'link': link},
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_password_reset_email(user, *, request=None, token: str) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse(
        'accounts_password_web_reset_confirm',
        kwargs={'uidb64': uid, 'token': token},
    )
    link = f'{_origin(request)}{path}'

    subject = 'Password reset request'
    body = render_to_string(
        'users/emails/password_reset.txt',
        {'user': user, 'link': link},
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def make_password_reset_token(user) -> str:
    return default_token_generator.make_token(user)
