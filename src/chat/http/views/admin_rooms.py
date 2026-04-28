from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db.models import Q

from chat.http.views.admin_users import superadmin_required
from chat.models import ChatRoom

ROOM_SORT_CHOICES = [
    ("-created_at", "Created (Newest First)"),
    ("created_at", "Created (Oldest First)"),
    ("name", "Name (A-Z)"),
    ("-name", "Name (Z-A)"),
    ("id", "ID (Low to High)"),
    ("-id", "ID (High to Low)"),
    ("is_deleted", "Status (Active First)"),
    ("-is_deleted", "Status (Deleted First)"),
]
ROOM_SORT_VALUES = {value for value, _ in ROOM_SORT_CHOICES}


@superadmin_required
def room_control_list(request):
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "-created_at")
    if sort not in ROOM_SORT_VALUES:
        sort = "-created_at"

    rooms_qs = ChatRoom.objects.all()
    if query:
        if query.isdigit():
            rooms_qs = rooms_qs.filter(Q(id=int(query)) | Q(name__icontains=query))
        else:
            rooms_qs = rooms_qs.filter(name__icontains=query)

    rooms_qs = rooms_qs.order_by(sort, "id")

    return render(
        request,
        "chat/admin_room_control_list.html",
        {
            "rooms": rooms_qs,
            "query": query,
            "sort": sort,
            "sort_options": ROOM_SORT_CHOICES,
        },
    )


@require_POST
@superadmin_required
def set_room_deleted_status(request, room_id):
    target_room = get_object_or_404(ChatRoom, id=room_id)
    is_deleted_raw = request.POST.get("is_deleted", "")
    is_deleted = is_deleted_raw in {"1", "true", "True", "on"}

    if is_deleted:
        target_room.soft_delete()
        status_label = "soft-deleted"
    else:
        target_room.restore()
        status_label = "restored"

    target_room.save(update_fields=["is_deleted", "deleted_at"])
    messages.success(request, f"Room '{target_room.name}' is now {status_label}.")

    redirect_query = request.POST.get("redirect_query", "")
    redirect_sort = request.POST.get("redirect_sort", "-created_at")
    query_string = urlencode({"q": redirect_query, "sort": redirect_sort})
    return HttpResponseRedirect(f"{reverse('admin-room-control-list')}?{query_string}")
