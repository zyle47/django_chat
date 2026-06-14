from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chat"

    def ready(self):
        from chat.signals import (
            profile_signals,  # noqa: F401
            room_signals,  # noqa: F401
        )
