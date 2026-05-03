from django.urls import re_path

from chat.ws.consumers import ChatConsumer, DMConsumer, LobbyConsumer

websocket_urlpatterns = [
    re_path(r"ws/lobby/$", LobbyConsumer.as_asgi()),
    re_path(r"ws/chat/(?P<room_name>[-a-zA-Z0-9_]+)/$", ChatConsumer.as_asgi()),
    re_path(r"ws/dm/(?P<peer_username>[\w.@+-]+)/$", DMConsumer.as_asgi()),
]
