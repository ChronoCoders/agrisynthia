import hashlib

import pyotp
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import BackupCode, UserProfile


class UserProfileSignalTests(TestCase):
    def test_profile_is_auto_created_on_user_signup(self):
        user = User.objects.create_user(username="alice", password="x" * 16)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_profile_defaults(self):
        user = User.objects.create_user(username="bob", password="x" * 16)
        p = user.profile
        self.assertFalse(p.email_verified)
        self.assertFalse(p.totp_enabled)
        self.assertEqual(p.language, "tr")
        self.assertTrue(p.ndvi_alert_enabled)


class BackupCodeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="codes", password="x" * 16)

    def test_generate_returns_eight_codes_and_persists_hashes(self):
        codes = BackupCode.generate_for_user(self.user)
        self.assertEqual(len(codes), 8)
        self.assertEqual(BackupCode.objects.filter(user=self.user).count(), 8)
        for code in codes:
            self.assertEqual(len(code), 8)
            expected_hash = hashlib.sha256(code.encode()).hexdigest()
            self.assertTrue(
                BackupCode.objects.filter(user=self.user, code_hash=expected_hash).exists()
            )

    def test_generate_replaces_existing(self):
        BackupCode.generate_for_user(self.user)
        first_hashes = set(BackupCode.objects.filter(user=self.user).values_list("code_hash", flat=True))
        BackupCode.generate_for_user(self.user)
        second_hashes = set(BackupCode.objects.filter(user=self.user).values_list("code_hash", flat=True))
        self.assertEqual(len(second_hashes), 8)
        self.assertFalse(first_hashes & second_hashes)

    def test_verify_consumes_code_once(self):
        codes = BackupCode.generate_for_user(self.user)
        self.assertTrue(BackupCode.verify(self.user, codes[0]))
        self.assertFalse(BackupCode.verify(self.user, codes[0]))

    def test_verify_rejects_unknown_code(self):
        BackupCode.generate_for_user(self.user)
        self.assertFalse(BackupCode.verify(self.user, "99999999"))

    def test_verify_is_user_scoped(self):
        other = User.objects.create_user(username="eve", password="x" * 16)
        codes = BackupCode.generate_for_user(self.user)
        self.assertFalse(BackupCode.verify(other, codes[0]))


class VerificationTokenTests(TestCase):
    def test_token_is_64_hex_chars(self):
        user = User.objects.create_user(username="tok", password="x" * 16)
        token = user.profile.generate_verification_token()
        self.assertEqual(len(token), 64)
        int(token, 16)
        self.assertEqual(user.profile.email_verification_token, token)


class RegistrationFlowTests(TestCase):
    def test_get_renders_form(self):
        resp = self.client.get(reverse("register"))
        self.assertEqual(resp.status_code, 200)

    def test_post_creates_user_and_redirects_to_login(self):
        resp = self.client.post(reverse("register"), {
            "username": "charlie",
            "password1": "Strong!Passw0rd",
            "password2": "Strong!Passw0rd",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("login"))
        self.assertTrue(User.objects.filter(username="charlie").exists())

    def test_post_does_not_auto_login(self):
        self.client.post(reverse("register"), {
            "username": "dora",
            "password1": "Strong!Passw0rd",
            "password2": "Strong!Passw0rd",
        })
        resp = self.client.get(reverse("account_settings"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_authenticated_user_is_redirected(self):
        User.objects.create_user(username="eve", password="Strong!Passw0rd")
        self.client.login(username="eve", password="Strong!Passw0rd")
        resp = self.client.get(reverse("register"))
        self.assertEqual(resp.status_code, 302)


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="frank", email="frank@example.com", password="Strong!Passw0rd"
        )
        self.token = self.user.profile.generate_verification_token()

    def test_valid_token_marks_email_verified(self):
        self.assertFalse(self.user.profile.email_verified)
        resp = self.client.get(reverse("verify_email", args=[self.token]))
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.email_verified)
        self.assertEqual(self.user.profile.email_verification_token, "")
        self.assertEqual(resp.status_code, 302)

    def test_invalid_token_does_not_verify(self):
        resp = self.client.get(reverse("verify_email", args=["a" * 64]))
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)
        self.assertEqual(resp.status_code, 302)

    def test_token_is_single_use(self):
        self.client.get(reverse("verify_email", args=[self.token]))
        resp = self.client.get(reverse("verify_email", args=[self.token]))
        self.assertEqual(resp.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.email_verified)


class TwoFactorSetupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gus", password="Strong!Passw0rd")
        self.client.login(username="gus", password="Strong!Passw0rd")

    def test_get_returns_qr_and_secret(self):
        resp = self.client.get(reverse("setup_2fa"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("qr_b64", resp.context)
        self.assertIn("totp_secret", resp.context)
        self.assertEqual(len(resp.context["totp_secret"]), 32)

    def test_post_with_valid_code_enables_2fa_and_returns_backup_codes(self):
        secret = pyotp.random_base32()
        valid_code = pyotp.TOTP(secret).now()
        resp = self.client.post(reverse("setup_2fa"), {
            "totp_secret": secret,
            "totp_code": valid_code,
        })
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.totp_enabled)
        self.assertEqual(self.user.profile.totp_secret, secret)
        self.assertEqual(BackupCode.objects.filter(user=self.user).count(), 8)
        self.assertIn("backup_codes", resp.context)

    def test_post_with_invalid_code_does_not_enable_2fa(self):
        secret = pyotp.random_base32()
        self.client.post(reverse("setup_2fa"), {
            "totp_secret": secret,
            "totp_code": "000000",
        })
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.totp_enabled)


class TwoFactorLoginInterceptionTests(TestCase):
    def test_login_without_2fa_completes_normally(self):
        User.objects.create_user(username="hank", password="Strong!Passw0rd")
        resp = self.client.post(reverse("login"), {
            "username": "hank",
            "password": "Strong!Passw0rd",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn(reverse("verify_2fa"), resp.url)
        self.assertTrue("_auth_user_id" in self.client.session)

    def test_login_with_2fa_redirects_to_verify(self):
        user = User.objects.create_user(username="ivy", password="Strong!Passw0rd")
        user.profile.totp_secret = pyotp.random_base32()
        user.profile.totp_enabled = True
        user.profile.save()

        resp = self.client.post(reverse("login"), {
            "username": "ivy",
            "password": "Strong!Passw0rd",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("verify_2fa"))
        self.assertNotIn("_auth_user_id", self.client.session)


class TwoFactorVerifyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jane", password="Strong!Passw0rd")
        self.secret = pyotp.random_base32()
        self.user.profile.totp_secret = self.secret
        self.user.profile.totp_enabled = True
        self.user.profile.save()

    def _start_pending_login(self):
        self.client.post(reverse("login"), {
            "username": "jane",
            "password": "Strong!Passw0rd",
        })

    def test_valid_totp_completes_login(self):
        self._start_pending_login()
        valid_code = pyotp.TOTP(self.secret).now()
        resp = self.client.post(reverse("verify_2fa"), {"code": valid_code})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_invalid_totp_does_not_log_in(self):
        self._start_pending_login()
        resp = self.client.post(reverse("verify_2fa"), {"code": "000000"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_valid_backup_code_completes_login_and_is_consumed(self):
        codes = BackupCode.generate_for_user(self.user)
        self._start_pending_login()
        resp = self.client.post(reverse("verify_2fa"), {"code": codes[0]})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)
        used = BackupCode.objects.get(
            user=self.user,
            code_hash=hashlib.sha256(codes[0].encode()).hexdigest(),
        )
        self.assertTrue(used.used)

    def test_direct_access_without_pending_login_redirects(self):
        resp = self.client.get(reverse("verify_2fa"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("login"))


class SettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="kate", email="kate@example.com", password="Strong!Passw0rd"
        )
        self.client.login(username="kate", password="Strong!Passw0rd")

    def test_get_renders(self):
        resp = self.client.get(reverse("account_settings"))
        self.assertEqual(resp.status_code, 200)

    def test_update_profile_changes_fields(self):
        resp = self.client.post(reverse("account_settings"), {
            "_action": "update_profile",
            "first_name": "Kate",
            "last_name": "Doe",
            "email": "kate@example.com",
            "phone": "+90 555 111 22 33",
            "language": "en",
        })
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Kate")
        self.assertEqual(self.user.profile.phone, "+90 555 111 22 33")
        self.assertEqual(self.user.profile.language, "en")

    def test_changing_email_resets_verification_and_sends_new_token(self):
        self.user.profile.email_verified = True
        self.user.profile.save()
        self.client.post(reverse("account_settings"), {
            "_action": "update_profile",
            "first_name": "",
            "last_name": "",
            "email": "kate-new@example.com",
            "phone": "",
            "language": "tr",
        })
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.email, "kate-new@example.com")
        self.assertFalse(self.user.profile.email_verified)

    def test_disable_2fa_with_wrong_password_rejected(self):
        self.user.profile.totp_enabled = True
        self.user.profile.totp_secret = pyotp.random_base32()
        self.user.profile.save()
        self.client.post(reverse("account_settings"), {
            "_action": "disable_2fa",
            "current_password_2fa": "wrong-password",
        })
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.totp_enabled)

    def test_disable_2fa_with_correct_password_clears_state(self):
        BackupCode.generate_for_user(self.user)
        self.user.profile.totp_enabled = True
        self.user.profile.totp_secret = pyotp.random_base32()
        self.user.profile.save()

        self.client.post(reverse("account_settings"), {
            "_action": "disable_2fa",
            "current_password_2fa": "Strong!Passw0rd",
        })
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.totp_enabled)
        self.assertEqual(self.user.profile.totp_secret, "")
        self.assertEqual(BackupCode.objects.filter(user=self.user).count(), 0)

    def test_update_notifications_changes_thresholds(self):
        self.client.post(reverse("account_settings"), {
            "_action": "update_notifications",
            "ndvi_alert_enabled": "on",
            "ndvi_alert_threshold_low": "0.25",
            "ndvi_alert_threshold_high": "0.75",
        })
        self.user.profile.refresh_from_db()
        self.assertAlmostEqual(self.user.profile.ndvi_alert_threshold_low, 0.25)
        self.assertAlmostEqual(self.user.profile.ndvi_alert_threshold_high, 0.75)


class AuthRequiredTests(TestCase):
    def test_settings_requires_login(self):
        resp = self.client.get(reverse("account_settings"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_setup_2fa_requires_login(self):
        resp = self.client.get(reverse("setup_2fa"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_send_verification_email_requires_login(self):
        resp = self.client.post(reverse("send_verification_email"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)
