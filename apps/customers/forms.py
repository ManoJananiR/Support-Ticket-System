from django import forms
from django.contrib.auth.hashers import make_password
from apps.accounts.models import User
from django.core.exceptions import ValidationError
import re

class CustomerCreationForm(forms.ModelForm):
    """
    Form for admin to create new customers.
    Includes all customer fields plus password fields.
    """
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        }),
        help_text="Password will be hashed and stored securely"
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone_number',
            'business_name', 'business_type', 'gst_number',
            'address', 'city', 'state', 'country', 'pincode'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'customer@example.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number'
            }),
            'business_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Business name'
            }),
            'business_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'gst_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'GST number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Street address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Pincode'
            }),
        }
    
    def clean_email(self):
        """Validate email is unique."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
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
        """Validate password match and strength."""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")
        
        if password:
            if len(password) < 8:
                raise ValidationError('Password must be at least 8 characters long.')
            if not any(char.isdigit() for char in password):
                raise ValidationError('Password must contain at least one number.')
            if not any(char.isupper() for char in password):
                raise ValidationError('Password must contain at least one uppercase letter.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the customer with hashed password."""
        user = super().save(commit=False)
        user.user_type = 'customer'
        user.set_password(self.cleaned_data['password'])
        user.is_active = True
        if commit:
            user.save()
        return user


class CustomerEditForm(forms.ModelForm):
    """
    Form for editing existing customers.
    Email is not editable as it's the username.
    """
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone_number',
            'business_name', 'business_type', 'gst_number',
            'address', 'city', 'state', 'country', 'pincode', 'is_active'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number'
            }),
            'business_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Business name'
            }),
            'business_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'gst_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'GST number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Street address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Pincode'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean_phone_number(self):
        """Validate phone number format."""
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove any non-digit characters
            phone = re.sub(r'\D', '', phone)
            if len(phone) < 10 or len(phone) > 15:
                raise ValidationError('Phone number must be between 10 and 15 digits.')
        return phone
    
    def clean_business_type(self):
        """Validate business type."""
        business_type = self.cleaned_data.get('business_type')
        # Business type can be null/empty
        return business_type
    
    def clean_gst_number(self):
        """Validate GST number format (optional)."""
        gst = self.cleaned_data.get('gst_number')
        if gst:
            # Basic GST validation (15 characters)
            if len(gst) != 15:
                raise ValidationError('GST number should be 15 characters long.')
        return gst


class CustomerFilterForm(forms.Form):
    """
    Form for filtering customers in list view.
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, email, phone, business...'
        })
    )
    business_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Business Types')] + list(User.BUSINESS_TYPE_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Status'),
            ('active', 'Active'),
            ('inactive', 'Inactive')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )


class CustomerBulkActionForm(forms.Form):
    """
    Form for bulk actions on customers.
    """
    ACTION_CHOICES = (
        ('activate', 'Activate Selected'),
        ('deactivate', 'Deactivate Selected'),
        ('export', 'Export Selected'),
        ('delete', 'Delete Selected'),
    )
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean_action(self):
        action = self.cleaned_data.get('action')
        if action not in dict(self.ACTION_CHOICES):
            raise ValidationError("Invalid action selected.")
        return action


class CustomerPasswordResetForm(forms.Form):
    """
    Form for admin to reset customer password.
    """
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        }),
        help_text="Password will be hashed and stored securely"
    )
    confirm_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError("Passwords do not match.")
        
        if new_password:
            if len(new_password) < 8:
                raise ValidationError('Password must be at least 8 characters long.')
            if not any(char.isdigit() for char in new_password):
                raise ValidationError('Password must contain at least one number.')
            if not any(char.isupper() for char in new_password):
                raise ValidationError('Password must contain at least one uppercase letter.')
        
        return cleaned_data
    
    def save(self, user):
        """Set the new password for the user."""
        user.set_password(self.cleaned_data['new_password'])
        user.save()
        return user

class CustomerImportForm(forms.Form):
    """
    Form for importing customers from Excel file.
    """
    excel_file = forms.FileField(
        label='Excel File',
        help_text='Upload an Excel file with customer data. Supported formats: .xlsx, .xls',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )
    
    sheet_name = forms.CharField(
        required=False,
        label='Sheet Name',
        help_text='Sheet name containing the data (leave empty for first sheet)',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sheet1'
        })
    )
    
    has_header = forms.BooleanField(
        required=False,
        initial=True,
        label='First row contains headers',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label='Update existing customers',
        help_text='If checked, update customers with matching emails',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )