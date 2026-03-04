"""
Signals for tickets app.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Ticket, TicketComment, TicketHistory
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for ticket post-save.
    """
    if created:
        logger.info(f"Ticket created: {instance.ticket_id}")
        # Create history entry
        TicketHistory.objects.create(
            ticket=instance,
            user=instance.created_by,
            action='created',
            changes={'title': instance.title}
        )


@receiver(post_save, sender=TicketComment)
def comment_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for comment post-save.
    """
    if created:
        logger.info(f"Comment added to ticket {instance.ticket.ticket_id}")
        # Create history entry
        TicketHistory.objects.create(
            ticket=instance.ticket,
            user=instance.user,
            action='comment_added',
            changes={'comment_type': instance.comment_type}
        )