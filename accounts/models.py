# -*- coding: utf-8 -*-
import hashlib
import secrets

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    LANGUAGE_CHOICES = [("tr", "Türkçe"), ("en", "English")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="tr")
    ndvi_alert_enabled = models.BooleanField(default=True)
    ndvi_alert_threshold_low = models.FloatField(default=0.2)
    ndvi_alert_threshold_high = models.FloatField(default=0.8)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=64, blank=True)
    totp_secret = models.CharField(max_length=32, blank=True)
    totp_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_user_profile"

    def __str__(self):
        return f"{self.user.username} profili"

    def generate_verification_token(self) -> str:
        token = secrets.token_hex(32)
        self.email_verification_token = token
        self.save(update_fields=["email_verification_token"])
        return token


class BackupCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="backup_codes")
    code_hash = models.CharField(max_length=64)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_backup_codes"

    def __str__(self):
        return f"BackupCode ({self.user.username}, used={self.used})"

    @classmethod
    def generate_for_user(cls, user, count: int = 8):
        """Generate `count` plaintext backup codes, store hashed. Returns plaintext list."""
        cls.objects.filter(user=user).delete()
        codes = []
        for _ in range(count):
            code = "".join(str(secrets.randbelow(10)) for _ in range(8))
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            cls.objects.create(user=user, code_hash=code_hash)
            codes.append(code)
        return codes

    @classmethod
    def verify(cls, user, submitted_code: str) -> bool:
        """Verify and consume a backup code. Returns True if valid."""
        code_hash = hashlib.sha256(submitted_code.encode()).hexdigest()
        bc = cls.objects.filter(user=user, code_hash=code_hash, used=False).first()
        if bc:
            bc.used = True
            bc.save(update_fields=["used"])
            return True
        return False


@receiver(post_save, sender=User)
def _auto_create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
