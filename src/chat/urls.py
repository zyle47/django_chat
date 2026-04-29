from django.urls import path

from chat.http.views import (
    delete_image,
    enter_room,
    index,
    room,
    room_control_list,
    serve_image,
    set_room_deleted_status,
    set_user_active_status,
    signup,
    signup_pending,
    upload_image,
    user_approval_list,
)

urlpatterns = [
    path("", index, name="index"),
    path("rooms/enter/", enter_room, name="enter-room"),
    path("signup/", signup, name="signup"),
    path("signup/pending/", signup_pending, name="signup-pending"),
    path("chat/<slug:room_name>/", room, name="room"),
    path("chat/<slug:room_name>/image/", upload_image, name="upload-image"),
    path("chat/image/<int:image_id>/", serve_image, name="serve-image"),
    path("chat/image/<int:image_id>/delete/", delete_image, name="delete-image"),
    path("control/users/", user_approval_list, name="admin-user-approval-list"),
    path("control/users/<int:user_id>/active/", set_user_active_status, name="admin-user-set-active"),
    path("control/rooms/", room_control_list, name="admin-room-control-list"),
    path("control/rooms/<int:room_id>/deleted/", set_room_deleted_status, name="admin-room-set-deleted"),
]
