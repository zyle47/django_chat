from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from chat.models import ChatRoom
from chat.services.room_access import grant_room_access


def index(request):
    rooms = ChatRoom.objects.filter(is_deleted=False)
    return render(request, "chat/index.html", {"rooms": rooms})


@require_POST
@login_required
def enter_room(request):
    raw_room_name = request.POST.get("room_name", "")
    room_name = slugify(raw_room_name)
    room_password = request.POST.get("room_password", "")

    if not room_name:
        messages.error(request, "Please enter a valid room name.")
        return redirect("index")

    room_obj = ChatRoom.objects.filter(name=room_name).first()
    if room_obj is None:
        if not room_password:
            messages.error(request, "New rooms must have a password.")
            return redirect("index")

        room_obj = ChatRoom(name=room_name)
        room_obj.set_password(room_password)
        room_obj.save()
        grant_room_access(request.session, room_obj.name)
        return redirect(reverse("room", kwargs={"room_name": room_obj.name}))

    if room_obj.is_deleted:
        messages.error(request, "This room is currently unavailable.")
        return redirect("index")

    if not room_obj.check_password(room_password):
        messages.error(request, "Invalid room password.")
        return redirect("index")

    grant_room_access(request.session, room_obj.name)
    return redirect(reverse("room", kwargs={"room_name": room_obj.name}))
