"""
Forms for user authentication and profile management.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import re
from .models import User

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    """
    Form for registering new users.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'})
    )
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'})
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'})
    )
    phone_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'})
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'password1', 'password2']

    def clean_email(self):
        """Validate email is unique."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email

    def clean_phone_number(self):
        """Validate phone number format."""
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove any non-digit characters
            phone = re.sub(r'\D', '', phone)
            if len(phone) < 10 or len(phone) > 15:
                raise ValidationError('Phone number must be between 10 and 15 digits.')
        return phone

    def save(self, commit=True):
        """Save the user with customer role by default."""
        user = super().save(commit=False)
        user.user_type = 'customer'  # Default to customer
        user.email_verified = False
        if commit:
            user.save()
        return user


class UserProfileForm(UserChangeForm):
    """
    Form for editing user profile.
    """
    password = None  # Remove password field from the form

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'profile_picture', 
                  'department', 'job_title', 'company', 'timezone', 'language']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'job_title': forms.TextInput(attrs={'class': 'form-control'}),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'timezone': forms.Select(attrs={'class': 'form-control'}),
            'language': forms.Select(attrs={'class': 'form-control'}),
        }


class UserLoginForm(forms.Form):
    """
    Form for user login.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    remember_me = forms.BooleanField(required=False, initial=False)


class PasswordResetRequestForm(forms.Form):
    """
    Form for requesting password reset.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email'})
    )

    def clean_email(self):
        """Validate email exists."""
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError('No user found with this email address.')
        return email


class SetPasswordForm(forms.Form):
    """
    Form for setting new password.
    """
    password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password'})
    )
    password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'})
    )

    def clean(self):
        """Validate passwords match."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError('Passwords do not match.')
        
        # Password strength validation
        if password1:
            if len(password1) < 8:
                raise ValidationError('Password must be at least 8 characters long.')
            if not any(char.isdigit() for char in password1):
                raise ValidationError('Password must contain at least one number.')
            if not any(char.isupper() for char in password1):
                raise ValidationError('Password must contain at least one uppercase letter.')

        return cleaned_data


class UserNotificationSettingsForm(forms.ModelForm):
    """
    Form for managing notification preferences.
    """
    class Meta:
        model = User
        fields = ['email_notifications', 'ticket_assigned_notifications', 'ticket_updated_notifications']
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ticket_assigned_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ticket_updated_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TwoFactorSetupForm(forms.Form):
    """
    Form for setting up two-factor authentication.
    """
    enable_2fa = forms.BooleanField(required=False, initial=False)
    verification_code = forms.CharField(
        required=False,
        max_length=6,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter 6-digit code'})
    )

class AgentCreateForm(UserCreationForm):
    """Form for creating new agents."""
    
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=False)
    department = forms.CharField(required=False)
    job_title = forms.CharField(required=False)
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 
                  'department', 'job_title', 'profile_picture', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'agent'
        user.is_staff = True
        if commit:
            user.save()
        return user


class AgentEditForm(forms.ModelForm):
    """Form for editing existing agents."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'profile_picture',
                  'department', 'job_title', 'is_active', 'email_notifications',
                  'ticket_assigned_notifications', 'ticket_updated_notifications']