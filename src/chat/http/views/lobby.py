from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncHour
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from chat.models import ChatImage, ChatMessage, ChatRoom, DailyStats
from chat.services.rate_limit import is_rate_limited
from chat.services.room_access import grant_room_access


@login_required
def index(request):
    rooms = ChatRoom.objects.filter(is_deleted=False)

    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    hourly_qs = (
        ChatMessage.objects
        .filter(created_at__gte=last_24h, is_deleted=False)
        .annotate(hour=TruncHour('created_at'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )
    slots = [0] * 24
    for entry in hourly_qs:
        idx = 23 - int((now - entry['hour']).total_seconds() // 3600)
        if 0 <= idx < 24:
            slots[idx] = entry['count']

    msgs_24h = sum(slots)
    historical = DailyStats.objects.aggregate(total=Sum('message_count'))['total'] or 0

    stats = {
        'messages_24h': msgs_24h,
        'messages_total': historical + msgs_24h,
        'live_images': ChatImage.objects.filter(expires_at__gt=now).count(),
        'rooms': rooms.count(),
        'hourly': slots,
    }

    return render(request, 'chat/index.html', {'rooms': rooms, 'stats': stats})


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

    rl_key = f'rl:room:{request.session.session_key}:{room_name}'
    if is_rate_limited(rl_key, 10, 300):
        messages.error(request, "Too many attempts. Try again in 5 minutes.")
        return redirect("index")

    if not room_obj.check_password(room_password):
        messages.error(request, "Invalid room password.")
        return redirect("index")

    grant_room_access(request.session, room_obj.name)
    return redirect(reverse("room", kwargs={"room_name": room_obj.name}))
