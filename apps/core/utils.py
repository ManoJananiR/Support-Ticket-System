"""
Core utility functions for the support ticket system.
"""

import logging
from django.utils import timezone
from django.urls import reverse
# REMOVED: from . import views  <- This line is causing circular import

logger = logging.getLogger(__name__)


# REMOVED ALL EMAIL FUNCTIONS (already done earlier)

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
    from django.db.models.functions import TruncDate
    
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