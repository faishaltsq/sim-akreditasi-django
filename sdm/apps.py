from django.apps import AppConfig


class SdmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sdm'

    def ready(self):
        from sdm import signals  # noqa: F401
