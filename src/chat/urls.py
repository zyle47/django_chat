from django.urls import path

from chat.http.views import (
    enter_room,
    index,
    room_control_list,
    room,
    set_room_deleted_status,
    set_user_active_status,
    signup,
    signup_pending,
    user_approval_list,
)

urlpatterns = [
    path("", index, name="index"),
    path("rooms/enter/", enter_room, name="enter-room"),
    path("signup/", signup, name="signup"),
    path("signup/pending/", signup_pending, name="signup-pending"),
    path("chat/<slug:room_name>/", room, name="room"),
    path("control/users/", user_approval_list, name="admin-user-approval-list"),
    path("control/users/<int:user_id>/active/", set_user_active_status, name="admin-user-set-active"),
    path("control/rooms/", room_control_list, name="admin-room-control-list"),
    path("control/rooms/<int:room_id>/deleted/", set_room_deleted_status, name="admin-room-set-deleted"),
]
