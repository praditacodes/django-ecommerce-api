from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .forms_web import PasswordSetFromEmailLinkForm
from .helpers import account_activation_token_ok, activate_user_after_email, decode_user_uid
from .serializers import (
    AddressSerializer,
    CustomTokenObtainPairSerializer,
    EmailVerifySerializer,
    PasswordResetConfirmAPISerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'jwt_login'


class CustomTokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'jwt_refresh'


class LogoutApiView(APIView):
    """Blacklist the refresh token handed by SPA/mobile clients."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'jwt_logout'

    def post(self, request, *args, **kwargs):
        refresh_value = request.data.get('refresh')
        if not refresh_value:
            return Response(
                {'detail': '`refresh` token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = RefreshToken(refresh_value)
        token.blacklist()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class RegisterApiView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'registration'

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data, context={'request': request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {'detail': 'Registration successful — check email to activate your account.'},
            status=status.HTTP_201_CREATED,
        )


class ProfileApiView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class AddressListCreateApiView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.addresses.all().order_by('-is_default', '-created_at')


class AddressRetrieveUpdateDestroyApiView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.addresses.all()


class PasswordResetRequestApiView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_request'

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'detail': 'If that email belongs to an active account '
                'you will receive recovery instructions shortly.'
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmApiView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmAPISerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Password updated.'}, status=status.HTTP_200_OK)


class EmailVerifyApiView(APIView):
    """Non-browser parity with the templated verification link."""

    def post(self, request, *args, **kwargs):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.activate()
        return Response(
            {'detail': 'Your account has been verified.'},
            status=status.HTTP_200_OK,
        )


class VerifyEmailBrowserView(View):
    template_success = 'users/verify_success.html'
    template_invalid = 'users/token_invalid.html'

    def get(self, request, uidb64: str, token: str):
        user = decode_user_uid(uidb64)

        if user is None or not account_activation_token_ok(user, token):
            return render(request, self.template_invalid)

        activate_user_after_email(user)
        return render(request, self.template_success, {'user': user})


class PasswordResetFromMailView(View):
    template_name = 'users/password_reset_confirm.html'
    invalid_template = 'users/token_invalid.html'
    success_url = reverse_lazy('accounts_password_reset_complete')

    def get(self, request, uidb64: str, token: str):
        user = decode_user_uid(uidb64)
        if user is None or not default_token_generator.check_token(user, token):
            return render(request, self.invalid_template)

        form = PasswordSetFromEmailLinkForm()
        return render(
            request,
            self.template_name,
            {'form': form, 'uidb64': uidb64, 'token': token},
        )

    def post(self, request, uidb64: str, token: str):
        user = decode_user_uid(uidb64)
        if user is None or not default_token_generator.check_token(user, token):
            return render(request, self.invalid_template)

        form = PasswordSetFromEmailLinkForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {'form': form, 'uidb64': uidb64, 'token': token},
            )

        user.set_password(form.cleaned_data['new_password'])
        user.save(update_fields=['password'])
        messages.success(
            request,
            'Password updated — you may sign in with your new credential.',
        )
        return redirect(self.success_url)


class PasswordResetDoneView(TemplateView):
    template_name = 'users/password_reset_complete.html'
