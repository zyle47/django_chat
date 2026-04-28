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

    users_qs = User.objects.all()
    if query:
        if query.isdigit():
            users_qs = users_qs.filter(Q(id=int(query)) | Q(username__icontains=query))
        else:
            users_qs = users_qs.filter(username__icontains=query)

    users_qs = users_qs.order_by(sort, "id")

    return render(
        request,
        "chat/admin_user_approval_list.html",
        {
            "users": users_qs,
            "query": query,
            "sort": sort,
            "sort_options": SORT_CHOICES,
        },
    )


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
