from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import Address

User = get_user_model()


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ('-date_joined',)
    list_display = (
        'username',
        'email',
        'phone_number',
        'email_verified',
        'is_staff',
        'is_active',
        'date_joined',
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'email_verified')
    search_fields = ('username', 'email', 'phone_number')

    fieldsets = tuple(UserAdmin.fieldsets) + (
        ('Contact', {'fields': ('phone_number',)}),
        ('Verification', {'fields': ('email_verified',)}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'recipient_name',
        'city',
        'country',
        'is_default',
        'created_at',
    )
    list_select_related = ('user',)
    search_fields = (
        'recipient_name',
        'address_line_1',
        'city',
        'user__username',
        'user__email',
    )
    readonly_fields = ('created_at', 'updated_at')

