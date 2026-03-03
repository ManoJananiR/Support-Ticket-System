"""
Forms for ticket creation and management.
"""

from django import forms
from django.conf import settings
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, HTML, Div
from crispy_forms.bootstrap import PrependedText, AppendedText, TabHolder, Tab
from .models import Ticket, TicketComment, Category, TicketTemplate
from taggit.forms import TagField
import logging

logger = logging.getLogger(__name__)


class TicketCreateForm(forms.ModelForm):
    """
    Form for creating new tickets.
    """
    tags = TagField(required=False, help_text="Comma-separated tags")
    cc_emails = forms.CharField(
        required=False,
        help_text="Comma-separated email addresses",
        widget=forms.TextInput(attrs={'placeholder': 'email1@example.com, email2@example.com'})
    )
    
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'category', 'priority', 'tags', 'cc_emails']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 8}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter categories to only show active ones
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['category'].empty_label = "Select a category"
        
        # Set up crispy forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'needs-validation'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Fieldset(
                'Basic Information',
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
    
    def clean_cc_emails(self):
        """Validate and parse CC emails."""
        cc_emails = self.cleaned_data.get('cc_emails', '')
        if not cc_emails:
            return []
        
        # Split by comma and clean
        emails = [email.strip() for email in cc_emails.split(',') if email.strip()]
        
        # Validate each email
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        
        valid_emails = []
        for email in emails:
            try:
                validate_email(email)
                valid_emails.append(email)
            except ValidationError:
                raise forms.ValidationError(f"Invalid email address: {email}")
        
        return valid_emails
    
    def save(self, commit=True):
        """Save the ticket with user information."""
        ticket = super().save(commit=False)
        ticket.created_by = self.user
        ticket.source = 'web'
        ticket.ip_address = self.get_client_ip()
        ticket.user_agent = self.get_user_agent()
        
        if commit:
            ticket.save()
            # Save tags
            self.save_m2m()
            
            # Save CC emails
            ticket.cc_emails = self.cleaned_data.get('cc_emails', [])
            ticket.save(update_fields=['cc_emails'])
            
            logger.info(f"Ticket created via form: {ticket.ticket_id}")
        
        return ticket
    
    def get_client_ip(self):
        """Get client IP address from request."""
        request = getattr(self, 'request', None)
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            return ip
        return None
    
    def get_user_agent(self):
        """Get user agent from request."""
        request = getattr(self, 'request', None)
        if request:
            return request.META.get('HTTP_USER_AGENT', '')
        return ''


class TicketUpdateForm(forms.ModelForm):
    """
    Form for updating existing tickets.
    """
    tags = TagField(required=False)
    
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'category', 'priority', 'status', 
                 'assigned_to', 'tags', 'internal_notes', 'due_by']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'internal_notes': forms.Textarea(attrs={'rows': 4, 'class': 'internal-notes'}),
            'due_by': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter querysets
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['assigned_to'].queryset = settings.AUTH_USER_MODEL.objects.filter(
            user_type__in=['agent', 'admin'], is_active=True
        )
        
        # Set up crispy forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            TabHolder(
                Tab(
                    'Basic Info',
                    'title',
                    'description',
                    Row(
                        Column('category', css_class='form-group col-md-6 mb-0'),
                        Column('priority', css_class='form-group col-md-6 mb-0'),
                        css_class='form-row'
                    ),
                    Row(
                        Column('status', css_class='form-group col-md-6 mb-0'),
                        Column('assigned_to', css_class='form-group col-md-6 mb-0'),
                        css_class='form-row'
                    ),
                    'tags',
                ),
                Tab(
                    'Internal Notes',
                    'internal_notes',
                    'due_by',
                ),
            ),
            Submit('submit', 'Update Ticket', css_class='btn btn-primary'),
            HTML("""<a href="{% url 'tickets:detail' ticket.ticket_id %}" class="btn btn-secondary">Cancel</a>""")
        )
        
        # Restrict status changes based on user role
        if self.user and not self.user.is_admin():
            # Non-admins can't change certain statuses
            restricted_statuses = ['closed', 'escalated']
            choices = [(k, v) for k, v in self.fields['status'].choices if k not in restricted_statuses]
            self.fields['status'].choices = choices
    
    def clean(self):
        """Validate the form data."""
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        
        # Additional validation based on status changes
        if status == 'resolved' and not cleaned_data.get('internal_notes'):
            self.add_warning('Please add internal notes explaining the resolution.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the ticket with change tracking."""
        ticket = super().save(commit=False)
        old_status = Ticket.objects.get(pk=ticket.pk).status if ticket.pk else None
        
        if commit:
            ticket.save()
            self.save_m2m()
            
            # Log status change
            if old_status and old_status != ticket.status:
                logger.info(f"Ticket {ticket.ticket_id} status changed from {old_status} to {ticket.status}")
            
            # Handle resolution
            if ticket.status == 'resolved' and not ticket.resolved_at:
                ticket.resolved_at = timezone.now()
                ticket.save(update_fields=['resolved_at'])
            
            # Handle closure
            if ticket.status == 'closed' and not ticket.closed_at:
                ticket.closed_at = timezone.now()
                ticket.save(update_fields=['closed_at'])
        
        return ticket


class TicketCommentForm(forms.ModelForm):
    """
    Form for adding comments to tickets.
    """
    class Meta:
        model = TicketComment
        fields = ['content', 'comment_type']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Write your comment here...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.ticket = kwargs.pop('ticket', None)
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
    
    def save(self, commit=True):
        """Save the comment with additional information."""
        comment = super().save(commit=False)
        comment.ticket = self.ticket
        comment.user = self.user
        
        # Set IP and user agent if available
        request = getattr(self, 'request', None)
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                comment.ip_address = x_forwarded_for.split(',')[0]
            else:
                comment.ip_address = request.META.get('REMOTE_ADDR')
            comment.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        if commit:
            comment.save()
            logger.info(f"Comment added to ticket {self.ticket.ticket_id} by {self.user.email}")
        
        return comment


class TicketSearchForm(forms.Form):
    """
    Form for searching and filtering tickets.
    """
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search tickets...'}))
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
        empty_label="All Categories"
    )
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=settings.AUTH_USER_MODEL.objects.filter(user_type__in=['agent', 'admin']),
        empty_label="Anyone"
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    tags = forms.CharField(required=False, help_text="Comma-separated tags")
    
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


class TicketTemplateForm(forms.ModelForm):
    """
    Form for creating/editing ticket templates.
    """
    class Meta:
        model = TicketTemplate
        fields = ['name', 'description', 'category', 'priority', 'subject_template', 'body_template', 'is_active']
        widgets = {
            'body_template': forms.Textarea(attrs={'rows': 10}),
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
    
    action = forms.ChoiceField(choices=ACTION_CHOICES, required=True)
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=settings.AUTH_USER_MODEL.objects.filter(user_type__in=['agent', 'admin']),
        empty_label="Select Agent"
    )
    status = forms.ChoiceField(required=False, choices=Ticket.STATUS_CHOICES)
    priority = forms.ChoiceField(required=False, choices=Ticket.PRIORITY_CHOICES)
    category = forms.ModelChoiceField(
        required=False,
        queryset=Category.objects.filter(is_active=True),
        empty_label="Select Category"
    )
    tags = forms.CharField(required=False, help_text="Comma-separated tags")
    
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