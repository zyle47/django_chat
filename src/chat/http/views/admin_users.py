from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from chat.models import UpgradeRequest, UserProfile

SORT_CHOICES = [
    ("-date_joined", "Joined (Newest First)"),
    ("date_joined", "Joined (Oldest First)"),
    ("username", "Username (A-Z)"),
    ("-username", "Username (Z-A)"),
    ("id", "ID (Low to High)"),
    ("-id", "ID (High to Low)"),
    ("is_active", "Status (Inactive First)"),
    ("-is_active", "Status (Active First)"),
]
SORT_VALUES = {value for value, _ in SORT_CHOICES}


def superadmin_required(view_fn):
    @wraps(view_fn)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("Superadmin access required.")
        return view_fn(request, *args, **kwargs)

    return wrapped


@superadmin_required
def user_approval_list(request):
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "-date_joined")
    if sort not in SORT_VALUES:
        sort = "-date_joined"

    users_qs = User.objects.select_related("profile").all()
    if query:
        if query.isdigit():
            users_qs = users_qs.filter(Q(id=int(query)) | Q(username__icontains=query))
        else:
            users_qs = users_qs.filter(username__icontains=query)

    users_qs = users_qs.order_by(sort, "id")

    pending_requests = UpgradeRequest.objects.filter(handled=False)
    # Build a dict: user_id -> most-recently-requested level (string)
    pending_level_by_user = {}
    for req in pending_requests:
        # UpgradeRequest ordering is -created_at, so first seen per user is the most recent
        if req.user_id not in pending_level_by_user:
            pending_level_by_user[req.user_id] = req.requested_level

    # Attach pending_upgrade_level as a dynamic attr on each user for template convenience
    users_list = list(users_qs)
    for u in users_list:
        u.pending_upgrade_level = pending_level_by_user.get(u.id)

    return render(
        request,
        "chat/admin_user_approval_list.html",
        {
            "users": users_list,
            "query": query,
            "sort": sort,
            "sort_options": SORT_CHOICES,
            "level_choices": UserProfile.LEVEL_CHOICES,
        },
    )


@require_POST
@superadmin_required
def delete_user(request, user_id):
    target_user = get_object_or_404(User, id=user_id)

    if target_user.is_superuser:
        messages.error(request, "Cannot delete a superadmin account.")
        return HttpResponseRedirect(reverse("admin-user-approval-list"))

    if target_user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return HttpResponseRedirect(reverse("admin-user-approval-list"))

    username = target_user.username
    target_user.delete()
    messages.success(request, f"User '{username}' has been permanently deleted.")

    redirect_query = request.POST.get("redirect_query", "")
    redirect_sort = request.POST.get("redirect_sort", "-date_joined")
    query_string = urlencode({"q": redirect_query, "sort": redirect_sort})
    return HttpResponseRedirect(f"{reverse('admin-user-approval-list')}?{query_string}")


@require_POST
@superadmin_required
def set_user_active_status(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    is_active_raw = request.POST.get("is_active", "")
    is_active = is_active_raw in {"1", "true", "True", "on"}

    if target_user == request.user and not is_active:
        messages.error(request, "You cannot deactivate your own superadmin account.")
        return HttpResponseRedirect(reverse("admin-user-approval-list"))

    target_user.is_active = is_active
    target_user.save(update_fields=["is_active"])

    status_label = "approved" if is_active else "disabled"
    messages.success(request, f"User '{target_user.username}' is now {status_label}.")

    redirect_query = request.POST.get("redirect_query", "")
    redirect_sort = request.POST.get("redirect_sort", "-date_joined")
    query_string = urlencode({"q": redirect_query, "sort": redirect_sort})
    return HttpResponseRedirect(f"{reverse('admin-user-approval-list')}?{query_string}")


@require_POST
@superadmin_required
def set_user_level(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    level = request.POST.get("level", "")
    valid_levels = {value for value, _ in UserProfile.LEVEL_CHOICES}

    if level not in valid_levels:
        messages.error(request, f"Invalid tier level: '{level}'.")
        redirect_query = request.POST.get("redirect_query", "")
        redirect_sort = request.POST.get("redirect_sort", "-date_joined")
        query_string = urlencode({"q": redirect_query, "sort": redirect_sort})
        return HttpResponseRedirect(
            f"{reverse('admin-user-approval-list')}?{query_string}"
        )

    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    profile.level = level
    profile.save(update_fields=["level"])

    # Mark all pending upgrade requests for this user as handled
    UpgradeRequest.objects.filter(user=target_user, handled=False).update(handled=True)

    messages.success(request, f"User '{target_user.username}' tier set to {level}.")

    redirect_query = request.POST.get("redirect_query", "")
    redirect_sort = request.POST.get("redirect_sort", "-date_joined")
    query_string = urlencode({"q": redirect_query, "sort": redirect_sort})
    return HttpResponseRedirect(f"{reverse('admin-user-approval-list')}?{query_string}")
