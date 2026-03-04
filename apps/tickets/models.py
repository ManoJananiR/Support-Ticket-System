"""
Tickets app models for support ticket management.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from taggit.managers import TaggableManager
import uuid
import os


def ticket_attachment_path(instance, filename):
    """Generate file path for ticket attachments."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('attachments', f"ticket_{instance.ticket.id}", filename)


class Category(models.Model):
    """Ticket categories for organization and routing."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children'
    )
    sla_response_time = models.DurationField(
        default=timezone.timedelta(hours=4)
    )
    sla_resolution_time = models.DurationField(
        default=timezone.timedelta(hours=48)
    )
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_full_path(self):
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name


class Ticket(models.Model):
    """Main Ticket model for support requests."""
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('critical', 'Critical'),
    )
    
    STATUS_CHOICES = (
        ('new', 'New'),
        ('open', 'Open'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('reopened', 'Reopened'),
        ('escalated', 'Escalated'),
    )
    
    SOURCE_CHOICES = (
        ('email', 'Email'),
        ('web', 'Web Portal'),
        ('phone', 'Phone'),
        ('api', 'API'),
    )
    
    ticket_id = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Relationships
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_tickets'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        limit_choices_to={'user_type__in': ['agent', 'admin']}
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tickets'
    )
    
    # Status and Priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='web')
    
    # Tags
    tags = TaggableManager(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    due_by = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    
    # SLA Tracking
    sla_response_due = models.DateTimeField(null=True, blank=True)
    sla_resolution_due = models.DateTimeField(null=True, blank=True)
    sla_response_breached = models.BooleanField(default=False)
    sla_resolution_breached = models.BooleanField(default=False)
    
    # Metrics
    response_time = models.DurationField(null=True, blank=True)
    resolution_time = models.DurationField(null=True, blank=True)
    reopen_count = models.IntegerField(default=0)
    
    # Additional data
    cc_emails = models.JSONField(default=list, blank=True)
    internal_notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket_id']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['created_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.ticket_id} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = self.generate_ticket_id()
        super().save(*args, **kwargs)
    
    def generate_ticket_id(self):
        today = timezone.now().strftime('%Y%m%d')
        last_ticket = Ticket.objects.filter(
            ticket_id__startswith=f'TKT-{today}'
        ).order_by('-ticket_id').first()
        
        if last_ticket:
            last_number = int(last_ticket.ticket_id.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f'TKT-{today}-{new_number:05d}'
    
    @property
    def is_overdue(self):
        return self.due_by and timezone.now() > self.due_by
    
    def check_sla_breaches(self):
        now = timezone.now()
        updated = False
        
        if (self.sla_response_due and now > self.sla_response_due 
            and not self.first_response_at and not self.sla_response_breached):
            self.sla_response_breached = True
            updated = True
        
        if (self.sla_resolution_due and now > self.sla_resolution_due 
            and self.status not in ['resolved', 'closed'] and not self.sla_resolution_breached):
            self.sla_resolution_breached = True
            updated = True
        
        if updated:
            self.save(update_fields=['sla_response_breached', 'sla_resolution_breached'])
        
        return updated


class TicketComment(models.Model):
    """Comments/replies on tickets."""
    
    COMMENT_TYPE_CHOICES = (
        ('public', 'Public Reply'),
        ('internal', 'Internal Note'),
    )
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ticket_comments'
    )
    comment_type = models.CharField(
        max_length=20,
        choices=COMMENT_TYPE_CHOICES,
        default='public'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.user.email} on {self.ticket.ticket_id}"


class TicketAttachment(models.Model):
    """File attachments for tickets."""
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    comment = models.ForeignKey(
        TicketComment,
        on_delete=models.CASCADE,
        related_name='attachments',
        null=True,
        blank=True
    )
    file = models.FileField(
        upload_to=ticket_attachment_path,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt', 'zip']
        )]
    )
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_attachments'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename


class TicketHistory(models.Model):
    """Track all changes to tickets for audit trail."""
    ACTION_CHOICES = (
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('assigned', 'Assigned'),
        ('status_changed', 'Status Changed'),
        ('comment_added', 'Comment Added'),
    )
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='history'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = 'Ticket histories'
        ordering = ['-timestamp']


# ADD THIS MISSING MODEL
class TicketTemplate(models.Model):
    """Predefined templates for common ticket types."""
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    priority = models.CharField(max_length=20, choices=Ticket.PRIORITY_CHOICES, default='medium')
    subject_template = models.CharField(max_length=255)
    body_template = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name