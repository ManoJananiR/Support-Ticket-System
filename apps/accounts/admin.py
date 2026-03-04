"""
Admin configuration for accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from .models import LoginHistory, PasswordReset

User = get_user_model()


class CustomUserAdmin(UserAdmin):
    """
    Custom admin for User model.
    """
    model = User
    list_display = ['email', 'first_name', 'last_name', 'user_type', 'is_active', 'date_joined']
    list_filter = ['user_type', 'is_active', 'email_verified']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number', 'profile_picture')}),
        ('Permissions', {'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Security', {'fields': ('email_verified', 'two_factor_enabled', 'account_locked', 'failed_login_attempts')}),
        ('Notifications', {'fields': ('email_notifications', 'ticket_assigned_notifications', 'ticket_updated_notifications')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'user_type'),
        }),
    )


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    """
    Admin for LoginHistory model.
    """
    list_display = ['user', 'login_time', 'ip_address', 'login_successful']
    list_filter = ['login_successful', 'login_time']
    search_fields = ['user__email', 'ip_address']
    readonly_fields = ['user', 'ip_address', 'user_agent', 'login_time', 'login_successful']


@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    """
    Admin for PasswordReset model.
    """
    list_display = ['user', 'created_at', 'expires_at', 'used']
    list_filter = ['used', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['user', 'token', 'created_at', 'expires_at', 'used', 'ip_address']


admin.site.register(User, CustomUserAdmin)