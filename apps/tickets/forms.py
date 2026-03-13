"""
Forms for ticket creation and management.
"""

from django import forms
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, HTML, Div
from crispy_forms.bootstrap import PrependedText, TabHolder, Tab
from taggit.forms import TagField
from .models import Ticket, TicketComment, Category, TicketTemplate
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class TicketCreateForm(forms.ModelForm):
    """
    Form for creating new tickets with customer contact fields.
    Used by both customers and admins when creating tickets.
    """
    tags = TagField(required=False, help_text="Comma-separated tags")
    cc_emails = forms.CharField(
        required=False,
        help_text="Comma-separated email addresses",
        widget=forms.TextInput(attrs={'placeholder': 'email1@example.com, email2@example.com', 'class': 'form-control'})
    )
    
    # Customer contact fields (editable - NO AUTO-FILL)
    customer_name = forms.CharField(
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter customer full name'
        }),
        label="Customer Name"
    )
    customer_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter customer email address'
        }),
        label="Customer Email"
    )
    customer_phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter customer phone number (optional)'
        }),
        label="Customer Phone"
    )
    
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'category', 'priority', 'tags', 'cc_emails']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 8, 'class': 'form-control', 'placeholder': 'Describe the issue in detail...'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter a descriptive title'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter categories to only show active ones
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['category'].empty_label = "Select a category"
        
        # If user is admin and a customer_id is provided, try to pre-fill
        if self.user and self.user.is_admin() and self.request:
            customer_id = self.request.GET.get('customer')
            if customer_id:
                try:
                    from apps.accounts.models import User
                    customer = User.objects.get(id=customer_id, user_type='customer')
                    self.fields['customer_name'].initial = customer.get_full_name() or customer.email
                    self.fields['customer_email'].initial = customer.email
                    self.fields['customer_phone'].initial = customer.phone_number
                except User.DoesNotExist:
                    pass
        
        # Set up crispy forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'needs-validation'
        self.helper.attrs = {'novalidate': ''}
        self.helper.layout = Layout(
            Fieldset(
                'Customer Contact Information',
                Row(
                    Column('customer_name', css_class='form-group col-md-4 mb-0'),
                    Column('customer_email', css_class='form-group col-md-4 mb-0'),
                    Column('customer_phone', css_class='form-group col-md-4 mb-0'),
                    css_class='form-row'
                ),
            ),
            Fieldset(
                'Ticket Information',
                'title',
                'description',
                Row(
                    Column('category', css_class='form-group col-md-6 mb-0'),
                    Column('priority', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
            ),
            Fieldset(
                'Additional Information',
                'tags',
                PrependedText('cc_emails', '@', placeholder='email@example.com'),
            ),
            Submit('submit', 'Create Ticket', css_class='btn btn-primary'),
            HTML("""<a href="{% url 'tickets:list' %}" class="btn btn-secondary">Cancel</a>""")
        )
    
    def clean_customer_email(self):
        """Validate email format."""
        email = self.cleaned_data.get('customer_email')
        if email:
            try:
                from django.core.validators import validate_email
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError("Please enter a valid email address.")
        return email
    
    def clean_cc_emails(self):
        """Validate and parse CC emails."""
        cc_emails = self.cleaned_data.get('cc_emails', '')
        if not cc_emails:
            return []
        
        emails = [email.strip() for email in cc_emails.split(',') if email.strip()]
        valid_emails = []
        for email in emails:
            try:
                from django.core.validators import validate_email
                validate_email(email)
                valid_emails.append(email)
            except ValidationError:
                raise forms.ValidationError(f"Invalid email address: {email}")
        
        return valid_emails
    
    def get_client_ip(self):
        """Get client IP address from request."""
        if self.request:
            x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = self.request.META.get('REMOTE_ADDR')
            return ip
        return None
    
    def get_user_agent(self):
        """Get user agent from request."""
        if self.request:
            return self.request.META.get('HTTP_USER_AGENT', '')
        return ''
    
    def save(self, commit=True):
        """Save the ticket with customer contact information."""
        ticket = super().save(commit=False)
        
        # Store customer contact info in metadata
        customer_info = {
            'name': self.cleaned_data.get('customer_name'),
            'email': self.cleaned_data.get('customer_email'),
            'phone': self.cleaned_data.get('customer_phone'),
        }
        ticket.metadata = customer_info  # Store in JSON field
        
        ticket.created_by = self.user
        ticket.source = 'web'
        ticket.ip_address = self.get_client_ip()
        ticket.user_agent = self.get_user_agent()
        
        if commit:
            ticket.save()
            self.save_m2m()
            
            cc_emails = self.cleaned_data.get('cc_emails', [])
            if cc_emails:
                ticket.cc_emails = cc_emails
                ticket.save(update_fields=['cc_emails'])
            
            logger.info(f"Ticket created via form: {ticket.ticket_id}")
        
        return ticket
    
class TicketUpdateForm(forms.ModelForm):
    """
    Form for updating existing tickets (admin use) - INCLUDES CONTACT FIELDS
    """
    tags = TagField(required=False)
    
    # Customer contact fields (editable)
    customer_name = forms.CharField(
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Customer full name'
        }),
        label="Customer Name"
    )
    customer_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Customer email address'
        }),
        label="Customer Email"
    )
    customer_phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Customer phone number'
        }),
        label="Customer Phone"
    )
    
    class Meta:
        model = Ticket
        fields = ['customer_name', 'customer_email', 'customer_phone',
                 'title', 'description', 'category', 'priority', 'status', 
                 'assigned_to', 'tags', 'internal_notes', 'due_by']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            'internal_notes': forms.Textarea(attrs={'rows': 4, 'class': 'internal-notes form-control'}),
            'due_by': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter querysets
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['assigned_to'].queryset = User.objects.filter(
            user_type__in=['agent', 'admin'], is_active=True
        )
        
        # IMPORTANT: Load existing metadata into form fields
        if self.instance and self.instance.pk:
            metadata = self.instance.metadata or {}
            self.fields['customer_name'].initial = metadata.get('name', '')
            self.fields['customer_email'].initial = metadata.get('email', '')
            self.fields['customer_phone'].initial = metadata.get('phone', '')
    
    def save(self, commit=True):
        """Save the ticket with updated contact information."""
        ticket = super().save(commit=False)
        
        # Ensure metadata is a dictionary
        if not ticket.metadata:
            ticket.metadata = {}
        elif isinstance(ticket.metadata, str):
            import json
            try:
                ticket.metadata = json.loads(ticket.metadata)
            except:
                ticket.metadata = {}
        
        # Update metadata with contact information
        ticket.metadata['name'] = self.cleaned_data.get('customer_name', '')
        ticket.metadata['email'] = self.cleaned_data.get('customer_email', '')
        ticket.metadata['phone'] = self.cleaned_data.get('customer_phone', '')
        
        if commit:
            ticket.save()
            self.save_m2m()
        
        return ticket
    
class TicketCommentForm(forms.ModelForm):
    """
    Form for adding comments to tickets.
    """
    class Meta:
        model = TicketComment
        fields = ['content', 'comment_type']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Write your comment here...'}),
            'comment_type': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.ticket = kwargs.pop('ticket', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Adjust comment type choices based on user role
        if self.user and not (self.user.is_agent() or self.user.is_admin()):
            # Customers can only post public comments
            self.fields['comment_type'].choices = [('public', 'Public Reply')]
            self.fields['comment_type'].widget = forms.HiddenInput()
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'content',
            'comment_type',
            Submit('submit', 'Post Comment', css_class='btn btn-primary'),
            HTML("""<button type="button" class="btn btn-secondary" onclick="window.history.back()">Cancel</button>""")
        )
    
    def get_client_ip(self):
        """Get client IP address from request."""
        if self.request:
            x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = self.request.META.get('REMOTE_ADDR')
            return ip
        return None
    
    def get_user_agent(self):
        """Get user agent from request."""
        if self.request:
            return self.request.META.get('HTTP_USER_AGENT', '')
        return ''
    
    def save(self, commit=True):
        """Save the comment with additional information."""
        comment = super().save(commit=False)
        comment.ticket = self.ticket
        comment.user = self.user
        
        # Set IP and user agent if available
        comment.ip_address = self.get_client_ip()
        comment.user_agent = self.get_user_agent()
        
        if commit:
            comment.save()
            logger.info(f"Comment added to ticket {self.ticket.ticket_id} by {self.user.email}")
        
        return comment


class TicketSearchForm(forms.Form):
    """
    Form for searching and filtering tickets.
    """
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search tickets...'}))
    status = forms.MultipleChoiceField(
        required=False,
        choices=Ticket.STATUS_CHOICES,
        widget=forms.CheckboxSelectMultiple
    )
    priority = forms.MultipleChoiceField(
        required=False,
        choices=Ticket.PRIORITY_CHOICES,
        widget=forms.CheckboxSelectMultiple
    )
    category = forms.ModelChoiceField(
        required=False,
        queryset=Category.objects.filter(is_active=True),
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(user_type__in=['agent', 'admin']),  # FIXED: Using User.objects
        empty_label="Anyone",
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
    tags = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Comma-separated tags'}))
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_class = 'form-inline'
        self.helper.layout = Layout(
            Row(
                Column('query', css_class='form-group col-md-4 mb-2'),
                Column('status', css_class='form-group col-md-2 mb-2'),
                Column('priority', css_class='form-group col-md-2 mb-2'),
                Column('category', css_class='form-group col-md-2 mb-2'),
                Column('assigned_to', css_class='form-group col-md-2 mb-2'),
                css_class='form-row'
            ),
            Row(
                Column('date_from', css_class='form-group col-md-2 mb-2'),
                Column('date_to', css_class='form-group col-md-2 mb-2'),
                Column('tags', css_class='form-group col-md-4 mb-2'),
                Column(
                    Submit('submit', 'Search', css_class='btn btn-primary'),
                    HTML("""<a href="{% url 'tickets:list' %}" class="btn btn-secondary ml-2">Clear</a>"""),
                    css_class='form-group col-md-4 mb-2'
                ),
                css_class='form-row'
            ),
        )


class TicketBulkActionForm(forms.Form):
    """
    Form for bulk actions on tickets.
    """
    ACTION_CHOICES = (
        ('assign', 'Assign to Agent'),
        ('change_status', 'Change Status'),
        ('change_priority', 'Change Priority'),
        ('change_category', 'Change Category'),
        ('add_tags', 'Add Tags'),
        ('export', 'Export Selected'),
        ('delete', 'Delete Selected'),
    )
    
    action = forms.ChoiceField(choices=ACTION_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-control'}))
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(user_type__in=['agent', 'admin']),  # FIXED: Using User.objects
        empty_label="Select Agent",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(required=False, choices=Ticket.STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    priority = forms.ChoiceField(required=False, choices=Ticket.PRIORITY_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    category = forms.ModelChoiceField(
        required=False,
        queryset=Category.objects.filter(is_active=True),
        empty_label="Select Category",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tags = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Comma-separated tags'}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-inline'
        self.helper.layout = Layout(
            Row(
                Column('action', css_class='form-group col-md-3 mb-2'),
                Column('assigned_to', css_class='form-group col-md-3 mb-2'),
                Column('status', css_class='form-group col-md-2 mb-2'),
                Column('priority', css_class='form-group col-md-2 mb-2'),
                Column('category', css_class='form-group col-md-2 mb-2'),
                css_class='form-row'
            ),
            Row(
                Column('tags', css_class='form-group col-md-6 mb-2'),
                Column(
                    Submit('submit', 'Apply to Selected', css_class='btn btn-primary'),
                    css_class='form-group col-md-6 mb-2'
                ),
                css_class='form-row'
            ),
        )
    
    def clean(self):
        """Validate that required fields are provided based on action."""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        if action == 'assign' and not cleaned_data.get('assigned_to'):
            raise forms.ValidationError("Please select an agent to assign tickets to.")
        
        if action == 'change_status' and not cleaned_data.get('status'):
            raise forms.ValidationError("Please select a status.")
        
        if action == 'change_priority' and not cleaned_data.get('priority'):
            raise forms.ValidationError("Please select a priority.")
        
        if action == 'change_category' and not cleaned_data.get('category'):
            raise forms.ValidationError("Please select a category.")
        
        return cleaned_data


class TicketTemplateForm(forms.ModelForm):
    """
    Form for creating/editing ticket templates.
    """
    class Meta:
        model = TicketTemplate
        fields = ['name', 'description', 'category', 'priority', 'subject_template', 'body_template', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'subject_template': forms.TextInput(attrs={'class': 'form-control'}),
            'body_template': forms.Textarea(attrs={'rows': 10, 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'name',
            'description',
            Row(
                Column('category', css_class='form-group col-md-6 mb-0'),
                Column('priority', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'subject_template',
            'body_template',
            'is_active',
            Submit('submit', 'Save Template', css_class='btn btn-primary'),
        )
    
    def save(self, commit=True):
        """Save the template with creator information."""
        template = super().save(commit=False)
        if not template.pk:  # Only set on creation
            template.created_by = self.user
        
        if commit:
            template.save()
            logger.info(f"Ticket template '{template.name}' saved by {self.user.email}")
        
        return template
    
class AgentTicketUpdateForm(forms.ModelForm):
    """
    Form for agents to update tickets - only status and due date
    """
    class Meta:
        model = Ticket
        fields = ['status', 'due_by']  # Only these two fields for agents
        widgets = {
            'due_by': forms.DateTimeInput(attrs={
                'type': 'datetime-local', 
                'class': 'form-control',
                'placeholder': 'Select due date and time'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'status': 'Update Status',
            'due_by': 'Due Date (Optional)'
        }
        help_texts = {
            'status': 'Change the current status of this ticket',
            'due_by': 'Set expected resolution date (optional)'
        }
    
    def __init__(self, *args, **kwargs):
        # Pop the 'user' keyword argument if it exists (to avoid errors)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Restrict status choices for agents
        self.fields['status'].choices = [
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('pending', 'Pending'),
            ('resolved', 'Resolved'),
        ]
        # Make status required, due_date optional
        self.fields['status'].required = True
        self.fields['due_by'].required = False