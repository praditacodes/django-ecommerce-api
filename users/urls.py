from django.urls import path

from .views import (
    AddressListCreateApiView,
    AddressRetrieveUpdateDestroyApiView,
    EmailVerifyApiView,
    LogoutApiView,
    PasswordResetConfirmApiView,
    PasswordResetRequestApiView,
    ProfileApiView,
    RegisterApiView,
)

urlpatterns = [
    path(
        'register/',
        RegisterApiView.as_view(),
        name='api_register',
    ),
    path(
        'profile/',
        ProfileApiView.as_view(),
        name='api_profile',
    ),
    path(
        'addresses/',
        AddressListCreateApiView.as_view(),
        name='api_address_list_create',
    ),
    path(
        'addresses/<int:pk>/',
        AddressRetrieveUpdateDestroyApiView.as_view(),
        name='api_address_detail',
    ),
    path(
        'logout/',
        LogoutApiView.as_view(),
        name='api_logout',
    ),
    path(
        'verify-email/',
        EmailVerifyApiView.as_view(),
        name='api_email_verify',
    ),
    path(
        'password/reset/request/',
        PasswordResetRequestApiView.as_view(),
        name='api_password_reset_request',
    ),
    path(
        'password/reset/confirm/',
        PasswordResetConfirmApiView.as_view(),
        name='api_password_reset_confirm',
    ),
]
