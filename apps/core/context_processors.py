"""
Context processors for templates.
"""

from django.conf import settings


def site_settings(request):
    """
    Add site settings to template context.
    """
    return {
        'SITE_NAME': 'Support Ticket System',
        'SITE_URL': settings.SITE_URL,
    }