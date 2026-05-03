"""Browser-oriented routes consumed by transactional email links."""

from django.urls import path, re_path

from .views import PasswordResetDoneView, PasswordResetFromMailView, VerifyEmailBrowserView

urlpatterns = [
    # Base64 tokens may contain characters `slug:` disallows — allow any segment except `/`.
    re_path(
        r'^verify-email/(?P<uidb64>[^/]+)/(?P<token>[^/]+)/$',
        VerifyEmailBrowserView.as_view(),
        name='accounts_verify_email',
    ),
    re_path(
        r'^password-reset/(?P<uidb64>[^/]+)/(?P<token>[^/]+)/$',
        PasswordResetFromMailView.as_view(),
        name='accounts_password_web_reset_confirm',
    ),
    path(
        'password-reset/done/',
        PasswordResetDoneView.as_view(),
        name='accounts_password_reset_complete',
    ),
]
