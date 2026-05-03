from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Address
from .notifications import make_password_reset_token, send_password_reset_email
from .tokens import account_activation_token

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds claims and enforces email verification for active accounts."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['username'] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # `self.user` is populated by TokenObtainSerializer after Django authenticates.
        if not getattr(self.user, 'email_verified', False):
            raise serializers.ValidationError(
                'Your email address is not verified yet. '
                'Check your inbox or use the verification link.'
            )

        return data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'phone_number']

    def validate_email(self, value):
        normalized = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError('That email address is already in use.')
        return normalized.lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('That username is already taken.')
        return value

    def create(self, validated_data):
        pw = validated_data.pop('password')
        request = self.context.get('request')

        with transaction.atomic():
            user = User.objects.create_user(
                password=pw,
                is_active=False,
                email_verified=False,
                **validated_data,
            )

        token = account_activation_token.make_token(user)

        def _send_verification():
            from .notifications import send_verification_email

            send_verification_email(user, request=request, token=token)

        transaction.on_commit(_send_verification)
        return user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'phone_number',
            'first_name',
            'last_name',
            'email_verified',
            'date_joined',
        ]
        read_only_fields = ('id', 'username', 'email', 'email_verified', 'date_joined')


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id',
            'label',
            'recipient_name',
            'phone',
            'address_line_1',
            'address_line_2',
            'city',
            'state_province',
            'postal_code',
            'country',
            'is_default',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_country(self, value: str):
        normalized = value.strip().upper()
        if len(normalized) != 2:
            raise serializers.ValidationError(
                'Use a two-letter ISO country code such as US or GB.'
            )
        return normalized

    def create(self, validated_data):
        user = self.context['request'].user
        is_default = validated_data.get('is_default')
        addr = Address.objects.create(user=user, **validated_data)
        if is_default:
            Address.objects.filter(user=user, is_default=True).exclude(pk=addr.pk).update(
                is_default=False
            )
        return addr

    def update(self, instance, validated_data):
        is_default = validated_data.get('is_default', instance.is_default)
        for field, val in validated_data.items():
            setattr(instance, field, val)
        instance.save()
        if is_default:
            Address.objects.filter(user=instance.user, is_default=True).exclude(
                pk=instance.pk
            ).update(is_default=False)
            instance.refresh_from_db()
        return instance


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        request = self.context.get('request')
        normalized = User.objects.normalize_email(self.validated_data['email']).lower()
        try:
            user = User.objects.get(email__iexact=normalized)
        except User.DoesNotExist:
            # Intentionally generic success on the caller so email addresses are not enumerated.
            return None

        if not getattr(user, 'email_verified', False) or not user.is_active:
            return None

        token = make_password_reset_token(user)
        transaction.on_commit(
            lambda: send_password_reset_email(user, request=request, token=token)
        )
        return user


class PasswordResetConfirmAPISerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError({'uid': ['Invalid reset link payload.']})

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({'token': ['Invalid or expired token.']})

        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class EmailVerifySerializer(serializers.Serializer):
    """Optional API-style verification when not using browser GET handler."""

    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError({'uid': ['Invalid activation link payload.']})

        if not account_activation_token.check_token(user, attrs['token']):
            raise serializers.ValidationError({'token': ['Invalid or expired token.']})

        attrs['user'] = user
        return attrs

    def activate(self):
        user = self.validated_data['user']
        user.is_active = True
        user.email_verified = True
        user.save(update_fields=['is_active', 'email_verified'])
        return user
