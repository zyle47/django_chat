from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from chat.services.realtime import publish_friends_changed

User = get_user_model()


@receiver(post_delete, sender=User)
def user_deleted(sender, instance, **kwargs):
    publish_friends_changed()


@receiver(post_save, sender=User)
def user_active_toggled(sender, instance, created, update_fields, **kwargs):
    if created:
        return
    if update_fields and "is_active" in update_fields:
        publish_friends_changed()
