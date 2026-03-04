"""
Core utility functions for the support ticket system.
"""

import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from celery import shared_task
from apps.accounts.models import User  # Add this import

logger = logging.getLogger(__name__)


def send_ticket_notification(ticket, event_type, comment=None):
    """
    Send email notifications for ticket events.
    
    Args:
        ticket: The ticket instance
        event_type: Type of event (created, updated, assigned, comment_added, etc.)
        comment: Optional comment instance
    """
    recipients = []
    
    # Determine recipients based on event type
    if event_type == 'created':
        # Notify assigned agent and admins
        if ticket.assigned_to and ticket.assigned_to.email_notifications:
            recipients.append(ticket.assigned_to.email)
        # Also notify admins
        admins = User.objects.filter(user_type='admin', email_notifications=True)
        recipients.extend([admin.email for admin in admins])
        
    elif event_type == 'assigned':
        # Notify the assigned agent
        if ticket.assigned_to and ticket.assigned_to.email_notifications:
            recipients.append(ticket.assigned_to.email)
            
    elif event_type == 'comment_added':
        # Notify all participants
        if comment and comment.comment_type == 'public':
            # Notify customer and assigned agent
            if ticket.created_by.email_notifications:
                recipients.append(ticket.created_by.email)
            if ticket.assigned_to and ticket.assigned_to.email_notifications:
                recipients.append(ticket.assigned_to.email)
            
            # Also notify anyone in CC
            recipients.extend(ticket.cc_emails)
    
    elif event_type == 'status_changed':
        # Notify customer
        if ticket.created_by.email_notifications:
            recipients.append(ticket.created_by.email)
        # Notify assigned agent
        if ticket.assigned_to and ticket.assigned_to.email_notifications:
            recipients.append(ticket.assigned_to.email)
    
    # Remove duplicates
    recipients = list(set(recipients))
    
    if recipients:
        try:
            # Send emails asynchronously
            send_notification_email.delay(
                ticket.id,
                event_type,
                comment.id if comment else None,
                recipients
            )
            logger.info(f"Notification queued for ticket {ticket.ticket_id} - {event_type} to {len(recipients)} recipients")
        except Exception as e:
            logger.error(f"Failed to queue notification: {str(e)}")
    
    return len(recipients)


@shared_task(bind=True, max_retries=3)
def send_notification_email(self, ticket_id, event_type, comment_id=None, recipients=None):
    """
    Celery task to send notification emails.
    """
    from apps.tickets.models import Ticket, TicketComment
    
    try:
        ticket = Ticket.objects.select_related(
            'created_by', 'assigned_to', 'category'
        ).get(id=ticket_id)
        
        comment = None
        if comment_id:
            comment = TicketComment.objects.select_related('user').get(id=comment_id)
        
        # Prepare email content
        subject = f"[{ticket.ticket_id}] {ticket.title}"
        
        # Generate ticket URL safely
        try:
            ticket_url = f"{settings.SITE_URL}{reverse('tickets:detail', args=[ticket.ticket_id])}"
        except:
            ticket_url = f"{settings.SITE_URL}/tickets/{ticket.ticket_id}/"
        
        context = {
            'ticket': ticket,
            'event_type': event_type,
            'comment': comment,
            'site_url': settings.SITE_URL,
            'ticket_url': ticket_url,
        }
        
        # Render email templates with fallback
        try:
            text_content = render_to_string(f'emails/ticket_{event_type}.txt', context)
            html_content = render_to_string(f'emails/ticket_{event_type}.html', context)
        except:
            # Fallback content if templates don't exist
            text_content = f"Ticket {ticket.ticket_id} - {event_type}\n\nView at: {ticket_url}"
            html_content = f"<h1>Ticket {ticket.ticket_id}</h1><p>{event_type}</p><p><a href='{ticket_url}'>View Ticket</a></p>"
        
        # Send email
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            recipients
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Notification email sent for ticket {ticket.ticket_id}")
        
    except Exception as e:
        logger.error(f"Failed to send notification email: {str(e)}")
        # Retry the task
        raise self.retry(exc=e, countdown=60)


@shared_task
def check_sla_breaches():
    """
    Scheduled task to check for SLA breaches.
    """
    from apps.tickets.models import Ticket
    
    tickets = Ticket.objects.exclude(
        status__in=['resolved', 'closed']
    ).select_related('assigned_to', 'created_by')
    
    breached_tickets = []
    
    for ticket in tickets:
        if ticket.check_sla_breaches():
            breached_tickets.append(ticket)
            
            # Send notification for breached SLA
            send_ticket_notification(ticket, 'sla_breached')
    
    logger.info(f"SLA check completed. Found {len(breached_tickets)} breached tickets.")
    return len(breached_tickets)


def log_activity(user, action, details=None):
    """
    Log user activity.
    """
    logger.info(f"User {user.email} - {action}" + (f": {details}" if details else ""))


def get_client_ip(request):
    """
    Get client IP address from request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def format_timedelta(td):
    """
    Format timedelta for display.
    """
    if not td:
        return "N/A"
    
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 24:
        days = hours // 24
        hours = hours % 24
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def generate_ticket_stats(user):
    """
    Generate ticket statistics for dashboard.
    """
    from apps.tickets.models import Ticket
    from django.db.models import Count, Q
    from datetime import timedelta
    
    if user.is_admin():
        tickets = Ticket.objects.all()
    elif user.is_agent():
        tickets = Ticket.objects.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True)
        )
    else:
        tickets = Ticket.objects.filter(created_by=user)
    
    now = timezone.now()
    last_week = now - timedelta(days=7)
    
    # Safe way to get daily trend without using extra()
    from django.db.models.functions import TruncDate
    
    trend = tickets.filter(
        created_at__gte=last_week
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    stats = {
        'total': tickets.count(),
        'open': tickets.filter(status__in=['new', 'open', 'in_progress']).count(),
        'pending': tickets.filter(status='pending').count(),
        'resolved': tickets.filter(status='resolved').count(),
        'closed': tickets.filter(status='closed').count(),
        
        'by_priority': list(tickets.values('priority').annotate(
            count=Count('id')
        ).order_by('priority')),
        
        'by_status': list(tickets.values('status').annotate(
            count=Count('id')
        ).order_by('status')),
        
        'trend': list(trend),
    }
    
    return stats