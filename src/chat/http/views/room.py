from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.text import slugify

from chat.models import ChatRoom
from chat.services.room_access import has_room_access
from chat.services.room_colors import room_color_for_username


@login_required
def room(request, room_name):
    normalized_room_name = slugify(room_name)
    if not normalized_room_name:
        messages.error(request, "Invalid room name.")
        return redirect("index")

    room_obj = ChatRoom.objects.filter(name=normalized_room_name, is_deleted=False).first()
    if room_obj is None:
        messages.error(request, "Room does not exist or is unavailable.")
        return redirect("index")

    if not has_room_access(request.session, room_obj.name):
        messages.error(request, "Enter room password from the lobby to access this room.")
        return redirect("index")

    recent_messages = room_obj.messages.order_by("-created_at")[:50]
    message_rows = []
    for entry in reversed(recent_messages):
        message_rows.append(
            {
                "username": entry.username,
                "message": entry.message,
                "created_at": entry.created_at,
                "color": room_color_for_username(room_obj.name, entry.username),
            }
        )

    context = {
        "room_name": room_obj.name,
        "messages": message_rows,
        "username": request.user.username,
    }
    return render(request, "chat/room.html", context)
