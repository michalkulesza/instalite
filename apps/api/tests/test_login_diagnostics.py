import unittest
from unittest.mock import patch

from instalite_api import instagram


class NeedsUpgrade(Exception):
    error_type = "needs_upgrade"

    def __str__(self) -> str:
        return "Your version of Instagram is out of date. Please upgrade your app to log in to Instagram."


class CaaFailureClient:
    def bloks_caa_login(self, *args, **kwargs):
        raise NeedsUpgrade()

    def login_legacy(self, *args, **kwargs):
        raise AssertionError("legacy login must not run")

    def login(self, *args, **kwargs):
        return self.bloks_caa_login()


class FallbackFailureClient:
    def _caa_result_action_markers(self, outcome):
        return ["CAA_LOGIN_FALLBACK:fallback_triggered"]

    def _extract_two_step_verification_context(self, outcome):
        return "opaque-secret-context"

    def bloks_caa_login(self, *args, **kwargs):
        return {"logged_in": False, "result": {}}

    def login_legacy(self, *args, **kwargs):
        raise NeedsUpgrade()

    def login(self, *args, **kwargs):
        self.bloks_caa_login()
        return self.login_legacy()


class LoginDiagnosticTests(unittest.TestCase):
    def _diagnostic_from(self, client_type):
        with patch.object(instagram, "Client", client_type):
            adapter = instagram.InstagramAdapter()
            with self.assertRaises(instagram.InstagramProviderCompatibilityError) as raised:
                adapter.login("test-user", "test-password")
        return raised.exception.diagnostic

    def test_caa_needs_upgrade_has_no_raw_response_data(self):
        diagnostic = self._diagnostic_from(CaaFailureClient)
        self.assertEqual(diagnostic["code"], "instagram_login.caa_needs_upgrade")
        self.assertEqual(diagnostic["failurePhase"], "caa")
        self.assertTrue(diagnostic["caaAttempted"])
        self.assertFalse(diagnostic["legacyAttempted"])
        self.assertEqual(diagnostic["diagnosis"], "not_available")
        self.assertNotIn("test-password", repr(diagnostic))

    def test_fallback_and_two_factor_context_are_reported_as_booleans(self):
        diagnostic = self._diagnostic_from(FallbackFailureClient)
        self.assertEqual(diagnostic["code"], "instagram_login.legacy_needs_upgrade")
        self.assertTrue(diagnostic["caaFallbackRequested"])
        self.assertTrue(diagnostic["caaTwoFactorContext"])
        self.assertEqual(diagnostic["diagnosis"], "indeterminate")
        self.assertNotIn("opaque-secret-context", repr(diagnostic))
