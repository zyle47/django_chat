from django.urls import re_path

from chat.ws.consumers import ChatConsumer, LobbyConsumer

websocket_urlpatterns = [
    re_path(r"ws/lobby/$", LobbyConsumer.as_asgi()),
    re_path(r"ws/chat/(?P<public_id>[0-9a-f]{64})/$", ChatConsumer.as_asgi()),
]
