from django.apps import AppConfig


class ApplsdConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'AppLSD'
    def ready(self):
        import AppLSD.signals
