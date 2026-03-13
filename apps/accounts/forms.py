"""
Forms for user authentication and profile management.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User
from django.core.exceptions import ValidationError
import re


class AdminCustomerCreationForm(forms.ModelForm):
    """
    Form for admin to create customer accounts with business details.
    """
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Password will be hashed and stored securely"
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone_number',
            'business_name', 'business_type', 'gst_number',
            'address', 'city', 'state', 'country', 'pincode'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'business_type': forms.Select(attrs={'class': 'form-control'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
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
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")
        
        # Password strength validation
        if password:
            if len(password) < 8:
                raise ValidationError('Password must be at least 8 characters long.')
            if not any(char.isdigit() for char in password):
                raise ValidationError('Password must contain at least one number.')
            if not any(char.isupper() for char in password):
                raise ValidationError('Password must contain at least one uppercase letter.')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'customer'
        user.set_password(self.cleaned_data['password'])
        user.is_active = True
        if commit:
            user.save()
        return user

# ADD THESE MISSING FORMS
class AgentCreateForm(UserCreationForm):
    """
    Form for creating new agents.
    """
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
    """
    Form for editing existing agents.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'profile_picture',
                  'department', 'job_title', 'is_active', 'email_notifications',
                  'ticket_assigned_notifications', 'ticket_updated_notifications']


class CustomerFilterForm(forms.Form):
    """Form for filtering customers in admin panel."""
    
    business_type = forms.ChoiceField(
        choices=[('', 'All')] + list(User.BUSINESS_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search by name, email, business...'})
    )


class UserProfileForm(UserChangeForm):
    """
    Form for editing user profile with better file handling.
    """
    password = None  # Remove password field from the form
    
    # Add a custom field to show current picture
    current_picture = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        label="Current Picture"
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'profile_picture', 
                  'business_name', 'business_type', 'gst_number',
                  'address', 'city', 'state', 'country', 'pincode']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'business_type': forms.Select(attrs={'class': 'form-control'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the current picture value
        if self.instance and self.instance.profile_picture:
            self.fields['current_picture'].initial = self.instance.profile_picture.name.split('/')[-1]
        else:
            self.fields['current_picture'].initial = 'No picture uploaded'
            
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