from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase

from accounts.models import BackupCode

WRONG_CODE = "not-a-real-code"


class InterleavedVerify:
    # Fires once, on the first write the outer verify issues, and runs a second
    # verify of the same code to completion before that write reaches the
    # database. Arming on the write rather than on the first statement is what
    # makes the race visible: if the nested call ran before the outer SELECT,
    # the outer would find the row already used and report a clean single
    # success, which is indistinguishable from a correct implementation.
    def __init__(self, user, code):
        self.user = user
        self.code = code
        self.armed = True
        self.inside = False
        self.ran = False
        self.result = None

    def __call__(self, execute, sql, params, many, context):
        if self.armed and not self.inside and sql.lstrip().upper().startswith("UPDATE"):
            self.armed = False
            self.inside = True
            try:
                self.result = BackupCode.verify(self.user, self.code)
                self.ran = True
            finally:
                self.inside = False
        return execute(sql, params, many, context)


class BackupCodeConcurrencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="password")
        self.codes = BackupCode.generate_for_user(self.user)
        self.code = self.codes[0]

    def _unused(self):
        return BackupCode.objects.filter(user=self.user, used=False).count()

    def _used(self):
        return BackupCode.objects.filter(user=self.user, used=True).count()

    def _interleave(self, code):
        hook = InterleavedVerify(self.user, code)
        with connection.execute_wrapper(hook):
            outer = BackupCode.verify(self.user, code)
        return outer, hook

    def test_fresh_code_verifies_once(self):
        self.assertTrue(BackupCode.verify(self.user, self.code))
        self.assertEqual(self._used(), 1)

    def test_same_code_is_refused_the_second_time(self):
        BackupCode.verify(self.user, self.code)
        self.assertFalse(BackupCode.verify(self.user, self.code))
        self.assertEqual(self._used(), 1)

    def test_interleaved_consumption_succeeds_once(self):
        outer, hook = self._interleave(self.code)
        self.assertTrue(hook.ran)
        self.assertEqual(sorted([outer, hook.result]), [False, True])

    def test_interleave_consumes_one_code_per_success(self):
        before = self._unused()
        outer, hook = self._interleave(self.code)
        successes = [result for result in (outer, hook.result) if result is True]
        self.assertEqual(self._used(), len(successes))
        self.assertEqual(before - self._unused(), len(successes))

    def test_wrong_code_under_interleave_consumes_nothing(self):
        before = self._unused()
        outer, hook = self._interleave(WRONG_CODE)
        self.assertFalse(outer)
        self.assertNotEqual(hook.result, True)
        self.assertEqual(self._used(), 0)
        self.assertEqual(self._unused(), before)
