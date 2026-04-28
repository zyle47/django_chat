from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

SIGNUP_PENDING_SESSION_KEY = "signup_pending_allowed"


def signup(request):
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.is_active = False
            user.save(update_fields=["is_active"])
            request.session[SIGNUP_PENDING_SESSION_KEY] = True
            return redirect("signup-pending")
    else:
        form = UserCreationForm()

    return render(request, "chat/signup.html", {"form": form})


def signup_pending(request):
    if request.user.is_authenticated:
        return redirect("index")

    if not request.session.pop(SIGNUP_PENDING_SESSION_KEY, False):
        return redirect("signup")

    return render(request, "chat/signup_pending.html")
