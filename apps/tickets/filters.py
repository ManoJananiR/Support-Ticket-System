"""
Advanced filtering for tickets - Alternative implementation without django-filter.
"""

from django.db import models
from django import forms
from django.utils import timezone
from .models import Ticket, Category
from apps.accounts.models import User


class TicketFilter:
    """
    Filter class for tickets (manual implementation).
    """
    
    def __init__(self, data, queryset, request=None):
        self.data = data
        self.queryset = queryset
        self.request = request
        self.form = self.get_form()
        
    def get_form(self):
        """Create a form for filter inputs."""
        return TicketFilterForm(self.data)
    
    def filter_queryset(self):
        """Apply filters to queryset."""
        queryset = self.queryset
        form = self.form
        
        if not form.is_valid():
            return queryset
        
        data = form.cleaned_data
        
        # Search filter
        search = data.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(ticket_id__icontains=search) |
                models.Q(title__icontains=search) |
                models.Q(description__icontains=search)
            )
        
        # Status filter
        status = data.get('status')
        if status:
            queryset = queryset.filter(status__in=status)
        
        # Priority filter
        priority = data.get('priority')
        if priority:
            queryset = queryset.filter(priority__in=priority)
        
        # Category filter
        category = data.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Assigned to filter
        assigned_to = data.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to=assigned_to)
        
        # Created by filter
        created_by = data.get('created_by')
        if created_by:
            queryset = queryset.filter(created_by=created_by)
        
        # Date filters
        created_after = data.get('created_after')
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        created_before = data.get('created_before')
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        # Overdue filter
        overdue = data.get('overdue')
        if overdue:
            queryset = queryset.filter(
                due_by__lt=timezone.now()
            ).exclude(status__in=['resolved', 'closed'])
        
        # Unassigned filter
        unassigned = data.get('unassigned')
        if unassigned:
            queryset = queryset.filter(assigned_to__isnull=True)
        
        # SLA breach filters
        if data.get('sla_response_breached'):
            queryset = queryset.filter(sla_response_breached=True)
        
        if data.get('sla_resolution_breached'):
            queryset = queryset.filter(sla_resolution_breached=True)
        
        # Tags filter
        tags = data.get('tags')
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            if tag_list:
                queryset = queryset.filter(tags__name__in=tag_list).distinct()
        
        return queryset.distinct()
    
    @property
    def qs(self):
        """Property to get filtered queryset."""
        return self.filter_queryset()


class TicketFilterForm(forms.Form):
    """Form for ticket filtering."""
    
    search = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'placeholder': 'Search by ID, title, or description', 'class': 'form-control'}
    ))
    
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
        queryset=User.objects.filter(user_type__in=['agent', 'admin']),
        empty_label="All Agents",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    created_by = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(is_active=True),
        empty_label="All Customers",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    created_after = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    
    created_before = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    
    overdue = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    unassigned = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    sla_response_breached = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    sla_resolution_breached = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    
    tags = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'placeholder': 'Comma-separated tags', 'class': 'form-control'}
    ))