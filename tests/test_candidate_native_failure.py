from unittest import TestCase
from unittest.mock import patch
from research import run_v25_native as runner
from research.run_v25_native import completion_failure


class NativeFailureTests(TestCase):
    def test_missing_account_is_setup_failure_not_strategy_loss(self):
        result = completion_failure(
            "Accounts deleted due security reason\n"
            "Tester tester not started because the account is not specified",
            3294954943, False)
        self.assertEqual(result["category"], "TESTER_ACCOUNT_UNAVAILABLE")
        self.assertFalse(result["accepted"])
        self.assertFalse(result["strategy_result_available"])
        self.assertFalse(result["account_expiry_proven"])
        self.assertFalse(result["completion_observed"])
        self.assertNotIn("net", result)

    def test_other_failure_not_misclassified_as_account_failure(self):
        result = completion_failure("EA initialization failed", 1, False)
        self.assertEqual(result["category"], "NATIVE_COMPLETION_FAILED")
        self.assertIsNone(result["account_expiry_proven"])
        self.assertFalse(result["accepted"])

    def test_completion_does_not_accept_nonzero_exit(self):
        result = completion_failure("automatic testing finished", 1, True)
        self.assertTrue(result["completion_observed"])
        self.assertFalse(result["accepted"])

    def test_optimizer_requires_optimizer_completion(self):
        result = completion_failure("automatic testing finished", 1, True, optimize=True)
        self.assertFalse(result["completion_observed"])

    def test_bad_explicit_connection_login_rejected_before_any_artifact(self):
        for login in (0, -1, True, 1.5, "123"):
            with self.subTest(login=login), patch.object(runner, "freeze") as freeze:
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    runner.execute("r5_check", tester_login=login)
                freeze.assert_not_called()

    def test_login_provenance_and_retry_are_explicit(self):
        import inspect
        source = inspect.getsource(runner.execute)
        self.assertIn('signature["tester_connection_login"] = tester_login', source)
        self.assertIn("tester_login=tester_login", source)
        self.assertIn("Login={connection_login}", source)
        self.assertNotIn("Password=", source)
