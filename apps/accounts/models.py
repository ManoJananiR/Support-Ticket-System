"""
Accounts app models for user management with role-based access control.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _
import uuid
import logging

logger = logging.getLogger(__name__)


class CustomUserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier
    for authentication instead of username.
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        logger.info(f"User created: {email}")
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'admin')
        extra_fields.setdefault('email_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with role-based access control.
    Extends Django's AbstractUser to add custom fields.
    """
    
    USER_TYPE_CHOICES = (
        ('customer', 'Customer'),
        ('agent', 'Agent'),
        ('admin', 'Administrator'),
    )
    
    username = None  # Remove username field
    email = models.EmailField(_('email address'), unique=True)
    user_type = models.CharField(
        max_length=20, 
        choices=USER_TYPE_CHOICES, 
        default='customer',
        help_text=_('User role in the system')
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        blank=True, 
        null=True
    )
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True, null=True)
    company = models.CharField(max_length=200, blank=True, null=True)
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    last_activity = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Security fields
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    account_locked = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    ticket_assigned_notifications = models.BooleanField(default=True)
    ticket_updated_notifications = models.BooleanField(default=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email is already the USERNAME_FIELD
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.get_full_name() or self.email
    
    def get_full_name(self):
        """
        Return the full name of the user.
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email
    
    def get_short_name(self):
        """Return the short name of the user."""
        return self.first_name or self.email.split('@')[0]
    
    def is_customer(self):
        """Check if user is a customer."""
        return self.user_type == 'customer'
    
    def is_agent(self):
        """Check if user is an agent."""
        return self.user_type == 'agent'
    
    def is_admin(self):
        """Check if user is an admin."""
        return self.user_type == 'admin' or self.is_superuser
    
    def can_manage_tickets(self):
        """Check if user can manage tickets (agent or admin)."""
        return self.is_agent() or self.is_admin()
    
    def lock_account(self):
        """Lock the user account."""
        self.account_locked = True
        self.save(update_fields=['account_locked'])
        logger.warning(f"Account locked for user: {self.email}")
    
    def unlock_account(self):
        """Unlock the user account."""
        self.account_locked = False
        self.failed_login_attempts = 0
        self.save(update_fields=['account_locked', 'failed_login_attempts'])
        logger.info(f"Account unlocked for user: {self.email}")
    
    def update_last_activity(self):
        """Update user's last activity timestamp."""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)


class LoginHistory(models.Model):
    """
    Track user login history for security monitoring.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    login_time = models.DateTimeField(auto_now_add=True)
    login_successful = models.BooleanField(default=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    
    class Meta:
        verbose_name_plural = 'Login histories'
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['user', '-login_time']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.login_time}"


class PasswordReset(models.Model):
    """
    Track password reset requests.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_resets')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.created_at}"
    
    def is_valid(self):
        """Check if the reset token is still valid."""
        return not self.used and self.expires_at > timezone.now()