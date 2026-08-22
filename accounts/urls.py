from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("signup/invited/<str:token>/", views.invited_signup, name="invited-signup"),
    path("login/", views.StudioLoginView.as_view(), name="login"),
    path("logout/", views.StudioLogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("preferences/", views.preferences, name="preferences"),
    path("preferences/theme/", views.theme_preference, name="theme"),
    path(
        "password/change/",
        views.StudioPasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "password/change/done/",
        views.StudioPasswordChangeDoneView.as_view(),
        name="password-change-done",
    ),
    path("password/reset/", views.StudioPasswordResetView.as_view(), name="password-reset"),
    path(
        "password/reset/done/",
        views.StudioPasswordResetDoneView.as_view(),
        name="password-reset-done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        views.StudioPasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password/reset/complete/",
        views.StudioPasswordResetCompleteView.as_view(),
        name="password-reset-complete",
    ),
]
