from django.contrib import admin

from chat.models import ChatRoom


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
