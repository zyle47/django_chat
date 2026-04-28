from django.db.models.signals import post_save
from django.dispatch import receiver

from chat.models import ChatRoom
from chat.services.realtime import publish_room_created


@receiver(post_save, sender=ChatRoom)
def broadcast_room_creation(sender, instance, created, **kwargs):
    if created:
        publish_room_created(instance.name)
