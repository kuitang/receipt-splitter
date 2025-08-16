from django.apps import AppConfig
import logging


class ReceiptsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "receipts"
    
    def ready(self):
        """Called when Django is ready - log startup information"""
        from django.conf import settings
        logger = logging.getLogger('receipts')
        logger.info(f"🚀 Receipt Splitter started - DEBUG={settings.DEBUG}")
