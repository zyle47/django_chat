from django.contrib import admin

from chat.models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("room", "username", "created_at")
    list_filter = ("room", "created_at")
    search_fields = ("username", "message")
