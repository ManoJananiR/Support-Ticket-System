"""
Utility functions for tickets app.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def send_ticket_notification(ticket, event_type, comment=None):
    """
    Send email notification for ticket events.
    """
    try:
        subject = f"[{ticket.ticket_id}] Ticket {event_type}"
        
        context = {
            'ticket': ticket,
            'event_type': event_type,
            'comment': comment,
            'site_url': settings.SITE_URL,
        }
        
        # Determine recipients
        recipients = []
        if ticket.created_by and ticket.created_by.email_notifications:
            recipients.append(ticket.created_by.email)
        
        if ticket.assigned_to and ticket.assigned_to.email_notifications:
            recipients.append(ticket.assigned_to.email)
        
        # Send email
        if recipients:
            html_message = render_to_string(f'emails/ticket_{event_type}.html', context)
            send_mail(
                subject,
                '',
                settings.DEFAULT_FROM_EMAIL,
                recipients,
                html_message=html_message,
                fail_silently=True
            )
            
        logger.info(f"Notification sent for ticket {ticket.ticket_id}")
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")


def log_activity(user, action, details=None):
    """
    Log user activity.
    """
    logger.info(f"User {user.email} - {action}" + (f": {details}" if details else ""))