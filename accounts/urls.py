from django.contrib.auth import views as auth_views
from django.urls import path
from django_ratelimit.decorators import ratelimit

from . import views

_rl_pw_reset = ratelimit(key="ip", rate="5/m", method="POST", block=True)
_rl_pw_confirm = ratelimit(key="ip", rate="10/m", method="POST", block=True)

urlpatterns = [
    path(
        "login/",
        views.TwoFactorLoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),

    path(
        "password-reset/",
        _rl_pw_reset(auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            html_email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        )),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        _rl_pw_confirm(auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
        )),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url="/accounts/password-change/done/",
        ),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_change_done",
    ),

    path("profile/", views.profile, name="profile"),
    path("settings/", views.settings_view, name="account_settings"),

    path("send-verification-email/", views.send_verification_email_view, name="send_verification_email"),
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),

    path("2fa/setup/", views.setup_2fa, name="setup_2fa"),
    path("verify-2fa/", views.verify_2fa, name="verify_2fa"),
]
