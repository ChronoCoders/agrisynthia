# -*- coding: utf-8 -*-
import base64
import hashlib
import io
import logging
import sys
import uuid

import pyotp
import qrcode
from django import forms
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import activate
from django.views.decorators.http import require_http_methods
from PIL import Image

from .models import BackupCode, UserProfile

logger = logging.getLogger(__name__)

_SESSION_2FA_USER = "_2fa_pending_user_id"
_SESSION_2FA_BACKEND = "_2fa_pending_backend"
_SESSION_2FA_NEXT = "_2fa_pending_next"

# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class ProfileForm(forms.ModelForm):
    class Meta:
        from django.contrib.auth import get_user_model
        model = get_user_model()
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["phone", "language"]
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+90 5xx xxx xx xx"}),
            "language": forms.Select(attrs={"class": "form-control"}),
        }


class NotificationForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["ndvi_alert_enabled", "ndvi_alert_threshold_low", "ndvi_alert_threshold_high"]
        widgets = {
            "ndvi_alert_threshold_low": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0", "max": "1",
            }),
            "ndvi_alert_threshold_high": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0", "max": "1",
            }),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_profile(user: User) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _send_verification_email(user: User) -> None:
    profile = _get_or_create_profile(user)
    token = profile.generate_verification_token()
    link = f"/accounts/verify-email/{token}/"
    try:
        send_mail(
            subject="Agrisynthia — E-posta adresinizi doğrulayın",
            message=(
                f"Merhaba {user.get_full_name() or user.username},\n\n"
                f"E-posta adresinizi doğrulamak için aşağıdaki bağlantıya tıklayın:\n\n"
                f"https://agrisynthia.com{link}\n\n"
                "Bu bağlantıyı siz istemediyseniz bu e-postayı dikkate almayın.\n\n"
                "Agrisynthia Ekibi"
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )
        logger.info("Verification email sent to %s", user.email)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", user.email, e)


def _resize_avatar(image_file) -> InMemoryUploadedFile:
    """Validate MIME, resize to ≤400×400, return InMemoryUploadedFile (JPEG)."""
    import magic as libmagic

    raw = image_file.read(2048)
    image_file.seek(0)
    mime = libmagic.from_buffer(raw, mime=True)
    if mime not in ("image/jpeg", "image/png"):
        raise ValidationError("Sadece JPEG ve PNG formatları desteklenir.")
    if image_file.size > 5 * 1024 * 1024:
        raise ValidationError("Avatar boyutu 5 MB'dan küçük olmalıdır.")

    img = Image.open(image_file)
    img.thumbnail((400, 400), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85)
    output.seek(0)

    return InMemoryUploadedFile(
        output, "ImageField",
        f"{uuid.uuid4().hex}.jpg",
        "image/jpeg",
        sys.getsizeof(output),
        None,
    )


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

class TwoFactorLoginView(LoginView):
    """Django's LoginView extended to intercept when 2FA is enabled."""

    def form_valid(self, form):
        user = form.get_user()
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            profile = None

        if profile and profile.totp_enabled:
            self.request.session[_SESSION_2FA_USER] = user.pk
            self.request.session[_SESSION_2FA_BACKEND] = user.backend
            self.request.session[_SESSION_2FA_NEXT] = self.get_success_url()
            return redirect("verify_2fa")

        return super().form_valid(form)


def register(request):
    if request.user.is_authenticated:
        return redirect("account_settings")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            logger.info("New user registered: %s", user.username)
            if user.email:
                _send_verification_email(user)
            return redirect("login")
        else:
            logger.warning("Registration failed for: %s", request.POST.get("username"))
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {"form": form})


def profile(request):
    """Legacy profile URL — redirect to the new settings page."""
    return redirect("account_settings")


# ---------------------------------------------------------------------------
# Settings (master view — Profil / Güvenlik / Bildirimler tabs)
# ---------------------------------------------------------------------------

@login_required
def settings_view(request):
    user = request.user
    account_profile = _get_or_create_profile(user)
    active_tab = request.GET.get("tab", "profil")

    profile_form = ProfileForm(instance=user)
    userprofile_form = UserProfileForm(instance=account_profile)
    password_form = PasswordChangeForm(user=user)
    notification_form = NotificationForm(instance=account_profile)

    if request.method == "POST":
        action = request.POST.get("_action", "")

        # ── Profil update ──────────────────────────────────────────────────
        if action == "update_profile":
            old_email = user.email
            profile_form = ProfileForm(request.POST, instance=user)
            userprofile_form = UserProfileForm(request.POST, instance=account_profile)
            if profile_form.is_valid() and userprofile_form.is_valid():
                new_email = profile_form.cleaned_data["email"]
                profile_form.save()
                up = userprofile_form.save(commit=False)
                if new_email and new_email != old_email:
                    up.email_verified = False
                    up.save()
                    _send_verification_email(user)
                    messages.info(request, "E-posta adresiniz değiştirildi. Doğrulama e-postası gönderildi.")
                else:
                    up.save()
                    messages.success(request, "Profil bilgileri güncellendi.")

                language = userprofile_form.cleaned_data.get("language", "tr")
                activate(language)
                response = redirect(f"/accounts/settings/?tab=profil")
                response.set_cookie(
                    "agrisynthia_language", language,
                    max_age=365 * 24 * 3600,
                    httponly=False,
                )
                return response
            active_tab = "profil"

        # ── Avatar upload ──────────────────────────────────────────────────
        elif action == "upload_avatar":
            avatar_file = request.FILES.get("avatar")
            if not avatar_file:
                messages.error(request, "Lütfen bir görsel seçin.")
            else:
                try:
                    resized = _resize_avatar(avatar_file)
                    if account_profile.avatar:
                        try:
                            from django.core.files.storage import default_storage
                            default_storage.delete(account_profile.avatar.name)
                        except Exception:
                            pass
                    account_profile.avatar = resized
                    account_profile.save(update_fields=["avatar"])
                    messages.success(request, "Avatar güncellendi.")
                except ValidationError as e:
                    messages.error(request, str(e))
            return redirect("/accounts/settings/?tab=profil")

        # ── Password change ────────────────────────────────────────────────
        elif action == "change_password":
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "Şifre başarıyla değiştirildi.")
                return redirect("/accounts/settings/?tab=guvenlik")
            active_tab = "guvenlik"

        # ── Disable 2FA ────────────────────────────────────────────────────
        elif action == "disable_2fa":
            current_password = request.POST.get("current_password_2fa", "")
            if not user.check_password(current_password):
                messages.error(request, "Mevcut şifreniz hatalı.")
            else:
                account_profile.totp_enabled = False
                account_profile.totp_secret = ""
                account_profile.save(update_fields=["totp_enabled", "totp_secret"])
                BackupCode.objects.filter(user=user).delete()
                messages.success(request, "İki faktörlü kimlik doğrulama devre dışı bırakıldı.")
            return redirect("/accounts/settings/?tab=guvenlik")

        # ── Notification settings ──────────────────────────────────────────
        elif action == "update_notifications":
            notification_form = NotificationForm(request.POST, instance=account_profile)
            if notification_form.is_valid():
                notification_form.save()
                messages.success(request, "Bildirim tercihleri güncellendi.")
                return redirect("/accounts/settings/?tab=bildirimler")
            active_tab = "bildirimler"

    context = {
        "profile_form": profile_form,
        "userprofile_form": userprofile_form,
        "password_form": password_form,
        "notification_form": notification_form,
        "account_profile": account_profile,
        "active_tab": active_tab,
    }
    return render(request, "accounts/settings.html", context)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def send_verification_email_view(request):
    if not request.user.email:
        messages.error(request, "Hesabınızda kayıtlı bir e-posta adresi yok.")
    else:
        _send_verification_email(request.user)
        messages.success(request, "Doğrulama e-postası gönderildi.")
    return redirect("/accounts/settings/?tab=guvenlik")


def verify_email(request, token: str):
    try:
        profile = UserProfile.objects.get(email_verification_token=token)
    except UserProfile.DoesNotExist:
        messages.error(request, "Geçersiz veya süresi dolmuş doğrulama bağlantısı.")
        return redirect("login")

    if not profile.email_verified:
        profile.email_verified = True
        profile.email_verification_token = ""
        profile.save(update_fields=["email_verified", "email_verification_token"])
        messages.success(request, "E-posta adresiniz başarıyla doğrulandı.")

    if request.user.is_authenticated:
        return redirect("/accounts/settings/?tab=guvenlik")
    return redirect("login")


# ---------------------------------------------------------------------------
# 2FA — setup
# ---------------------------------------------------------------------------

@login_required
def setup_2fa(request):
    user = request.user
    account_profile = _get_or_create_profile(user)

    if request.method == "POST":
        code = request.POST.get("totp_code", "").strip()
        secret = request.POST.get("totp_secret", "").strip()

        if not secret:
            messages.error(request, "Geçersiz istek.")
            return redirect("setup_2fa")

        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            account_profile.totp_secret = secret
            account_profile.totp_enabled = True
            account_profile.save(update_fields=["totp_secret", "totp_enabled"])
            backup_codes = BackupCode.generate_for_user(user)
            messages.success(request, "2FA başarıyla etkinleştirildi.")
            return render(request, "accounts/2fa_backup_codes.html", {
                "backup_codes": backup_codes,
            })
        else:
            messages.error(request, "Geçersiz doğrulama kodu. Lütfen tekrar deneyin.")
            # Re-render with same secret so user doesn't have to scan again

    secret = pyotp.random_base32()
    totp_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email or user.username,
        issuer_name="Agrisynthia",
    )

    qr = qrcode.QRCode(version=1, box_size=8, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, "accounts/2fa_setup.html", {
        "qr_b64": qr_b64,
        "totp_secret": secret,
        "account_profile": account_profile,
    })


# ---------------------------------------------------------------------------
# 2FA — verify at login
# ---------------------------------------------------------------------------

def verify_2fa(request):
    pending_user_id = request.session.get(_SESSION_2FA_USER)
    pending_backend = request.session.get(_SESSION_2FA_BACKEND)

    if not pending_user_id:
        return redirect("login")

    try:
        user = User.objects.get(pk=pending_user_id)
    except User.DoesNotExist:
        return redirect("login")

    error = None

    if request.method == "POST":
        code = request.POST.get("code", "").strip().replace(" ", "")
        try:
            account_profile = user.profile
        except UserProfile.DoesNotExist:
            account_profile = None

        verified = False

        # Try TOTP first
        if account_profile and account_profile.totp_secret:
            totp = pyotp.TOTP(account_profile.totp_secret)
            if totp.verify(code, valid_window=1):
                verified = True

        # Try backup code
        if not verified:
            verified = BackupCode.verify(user, code)

        if verified:
            del request.session[_SESSION_2FA_USER]
            del request.session[_SESSION_2FA_BACKEND]
            next_url = request.session.pop(_SESSION_2FA_NEXT, "/")
            user.backend = pending_backend
            auth_login(request, user)
            return redirect(next_url)

        error = "Geçersiz kod. Lütfen tekrar deneyin."

    return render(request, "accounts/2fa_verify.html", {"error": error})
