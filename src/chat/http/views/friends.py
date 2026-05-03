from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from chat.models import DirectMessage, DMRead, FriendRequest, Friendship
from chat.services import dm as dm_svc
from chat.services import friends as friend_svc

User = get_user_model()


@require_GET
@login_required
def list_friends(request):
    me = request.user.id
    rows = (
        Friendship.objects
        .filter(
            Q(user_low_id=me, user_high__is_active=True)
            | Q(user_high_id=me, user_low__is_active=True)
        )
        .select_related("user_low", "user_high")
        .order_by("-created_at")
    )
    friends = []
    for f in rows:
        other = f.user_high if f.user_low_id == me else f.user_low
        friends.append({
            "id": other.id,
            "username": other.username,
            "since": f.created_at.isoformat(),
        })
    return JsonResponse({"friends": friends})


@require_GET
@login_required
def list_pending_requests(request):
    now = timezone.now()
    qs = (
        FriendRequest.objects
        .filter(
            to_user_id=request.user.id,
            expires_at__gt=now,
            from_user__is_active=True,
        )
        .select_related("from_user", "room")
        .order_by("-created_at")
    )
    items = [
        {
            "id": r.id,
            "from_username": r.from_user.username,
            "room_name": r.room.name if r.room_id else None,
            "expires_at": r.expires_at.isoformat(),
        }
        for r in qs
    ]
    return JsonResponse({"requests": items})


@require_POST
@login_required
def accept_pending(request):
    name = request.POST.get("from_username", "").strip()
    if not name:
        return HttpResponseBadRequest("missing from_username")
    result = friend_svc.accept_request(request.user.id, name)
    return JsonResponse(result, status=200 if result.get("ok") else 400)


@require_POST
@login_required
def reject_pending(request):
    name = request.POST.get("from_username", "").strip()
    if not name:
        return HttpResponseBadRequest("missing from_username")
    result = friend_svc.reject_request(request.user.id, name)
    return JsonResponse(result, status=200 if result.get("ok") else 400)


@require_GET
@login_required
def dm_history(request, peer_username):
    peer = User.objects.filter(username=peer_username, is_active=True).first()
    if peer is None:
        return JsonResponse({"error": "no such user"}, status=404)
    if peer.id == request.user.id:
        return JsonResponse({"error": "self"}, status=400)
    if not Friendship.exists_between(request.user.id, peer.id):
        return JsonResponse({"error": "not friends"}, status=403)

    low, high = DirectMessage.sort_pair(request.user.id, peer.id)
    now = timezone.now()
    qs = (
        DirectMessage.objects
        .filter(pair_low=low, pair_high=high, expires_at__gt=now, is_deleted=False)
        .order_by("created_at")
    )
    items = [
        {
            "id": m.id,
            "from_user_id": m.from_user_id,
            "from_username": request.user.username if m.from_user_id == request.user.id else peer.username,
            "message": m.message,
            "created_at": m.created_at.isoformat(),
            "expires_at": m.expires_at.isoformat(),
            "edited_at": m.edited_at.isoformat() if m.edited_at else None,
        }
        for m in qs
    ]
    my_read = (
        DMRead.objects
        .filter(user_id=request.user.id, peer_id=peer.id)
        .values_list("last_read_at", flat=True)
        .first()
    )
    dm_svc.mark_read(request.user.id, peer.id)
    peer_read = (
        DMRead.objects
        .filter(user_id=peer.id, peer_id=request.user.id)
        .values_list("last_read_at", flat=True)
        .first()
    )
    return JsonResponse({
        "messages": items,
        "peer_username": peer.username,
        "peer_last_read_at": peer_read.isoformat() if peer_read else None,
        "my_last_read_at": my_read.isoformat() if my_read else None,
    })


@require_GET
@login_required
def unread_count(request):
    return JsonResponse({"count": dm_svc.unread_conversation_count(request.user.id)})
