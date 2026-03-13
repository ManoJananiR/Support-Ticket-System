"""
Accounts app models for user management with role-based access control.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
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
    Custom User model with role-based access control and business fields.
    """
    
    USER_TYPE_CHOICES = (
        ('customer', 'Customer'),
        ('agent', 'Agent'),
        ('admin', 'Administrator'),
    )
    
    BUSINESS_TYPE_CHOICES = (
        ('finance', 'Finance'),
        ('service', 'Service'),
        ('retail', 'Retail'),
        ('manufacturing', 'Manufacturing'),
        ('technology', 'Technology'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('other', 'Other'),
    )
    
    username = None  # Remove username field
    email = models.EmailField(_('email address'), unique=True)
    user_type = models.CharField(
        max_length=20, 
        choices=USER_TYPE_CHOICES, 
        default='customer'
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        blank=True, 
        null=True
    )
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    
    # NEW: Customer password field for email authentication
    customer_password = models.CharField(
        max_length=128, 
        blank=True, 
        null=True,
        help_text="Password for customer email authentication"
    )
    
    # NEW BUSINESS FIELDS
    business_name = models.CharField(max_length=200, blank=True, null=True)
    business_type = models.CharField(
        max_length=50, 
        choices=BUSINESS_TYPE_CHOICES,
        blank=True, 
        null=True
    )
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)
    
    # Agent fields
    department = models.CharField(max_length=100, blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True, null=True)
    
    # Security fields
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    account_locked = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    ticket_assigned_notifications = models.BooleanField(default=True)
    ticket_updated_notifications = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
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
            models.Index(fields=['business_type']),
            models.Index(fields=['business_name']),
        ]
    
    def __str__(self):
        return self.get_full_name() or self.email
    
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email
    
    def is_customer(self):
        return self.user_type == 'customer'
    
    def is_agent(self):
        return self.user_type == 'agent'
    
    def is_admin(self):
        return self.user_type == 'admin' or self.is_superuser
    
    def can_manage_tickets(self):
        return self.is_agent() or self.is_admin()
    
    def get_business_display(self):
        """Return business info for display"""
        if self.business_name:
            business_type = self.get_business_type_display() if self.business_type else ''
            return f"{self.business_name} ({business_type})"
        return "Not specified"
    
    def set_customer_password(self, raw_password):
        """Set the customer password (using Django's password hashing)"""
        from django.contrib.auth.hashers import make_password
        self.customer_password = make_password(raw_password)
        self.save(update_fields=['customer_password'])
    
    def check_customer_password(self, raw_password):
        """Check if the provided password matches the stored hash"""
        from django.contrib.auth.hashers import check_password
        if self.customer_password:
            return check_password(raw_password, self.customer_password)
        return False
    
    def increment_failed_attempts(self):
        """Increment failed login attempts and lock account if needed"""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        
        # Lock account after 5 failed attempts
        if self.failed_login_attempts >= 5:
            self.account_locked = True
        self.save(update_fields=['failed_login_attempts', 'last_failed_login', 'account_locked'])
    
    def reset_failed_attempts(self):
        """Reset failed login attempts on successful login"""
        self.failed_login_attempts = 0
        self.account_locked = False
        self.save(update_fields=['failed_login_attempts', 'account_locked'])
    
    def can_login(self):
        """Check if user is allowed to login (exists in DB and is active)"""
        return self.is_active and self.pk is not None
        
class LoginHistory(models.Model):
    """
    Track user login history for security monitoring.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    login_time = models.DateTimeField(auto_now_add=True)
    login_successful = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = 'Login histories'
        ordering = ['-login_time']


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
    
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()