from django import forms
from django.utils.text import slugify


class EnterRoomForm(forms.Form):
    room_name = forms.CharField(
        max_length=80,
        error_messages={"required": "Please enter a valid room name."},
    )
    room_password = forms.CharField(max_length=128, required=False)
    message_lifetime = forms.CharField(required=False)

    def clean_room_name(self):
        slug = slugify(self.cleaned_data["room_name"])
        if not slug:
            raise forms.ValidationError("Please enter a valid room name.")
        return slug

    def clean_message_lifetime(self):
        raw = self.cleaned_data.get("message_lifetime", "")
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        return None
