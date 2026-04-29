from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from chat.http.views.auth import RateLimitedLoginView

urlpatterns = [
    path(f"{settings.ADMIN_URL}/", admin.site.urls),
    path("accounts/login/", RateLimitedLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("chat.urls")),
]
