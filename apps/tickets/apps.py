"""
App configuration for tickets app.
"""

from django.apps import AppConfig


class TicketsConfig(AppConfig):
    """
    Tickets app configuration.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tickets'
    
    def ready(self):
        """
        Import signals when app is ready.
        """
        import apps.tickets.signals