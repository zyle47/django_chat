from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from chat.services.rate_limit import is_rate_limited

SIGNUP_PENDING_SESSION_KEY = "signup_pending_allowed"


class RateLimitedLoginView(LoginView):
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username', '').strip()
        if username and is_rate_limited(f'rl:login:{username}', 10, 300):
            messages.error(request, 'Too many login attempts. Try again in 5 minutes.')
            return redirect('login')
        return super().post(request, *args, **kwargs)


def signup(request):
    if request.user.is_authenticated:
        return redirect("index")

    session_key = request.session.session_key or request.META.get('REMOTE_ADDR', 'x')
    if request.method == "POST":
        if is_rate_limited(f'rl:signup:{session_key}', 5, 3600):
            messages.error(request, 'Too many signup attempts. Try again later.')
            return redirect('signup')
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
