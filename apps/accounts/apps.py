"""
App configuration for accounts app.
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    Accounts app configuration.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    
    def ready(self):
        """
        Import signals when app is ready.
        """
        import apps.accounts.signals