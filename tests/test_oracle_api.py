import unittest
from unittest.mock import Mock, patch

import requests

from services.oracle_api import (
    InstanceUrlError,
    normalize_instance_url,
    test_connection,
)


class OracleConnectionTests(unittest.TestCase):
    def test_valid_url(self):
        self.assertEqual(
            normalize_instance_url("https://demo.fa.us2.oraclecloud.com/"),
            ("https://demo.fa.us2.oraclecloud.com", "demo.fa.us2.oraclecloud.com"),
        )

    def test_rejects_insecure_or_non_oracle_host(self):
        for value in (
            "http://demo.fa.us2.oraclecloud.com",
            "https://evil.example.com",
            "https://demo.fa.us2.oraclecloud.com:443",
            "https://demo.fa.us2.oraclecloud.com/other",
            "https://demo.fa.us2.oraclecloud.com?redirect=1",
            "https://demo.fa.us2.oraclecloud.com@evil.example.com",
        ):
            with self.subTest(value=value):
                with self.assertRaises(InstanceUrlError):
                    normalize_instance_url(value)

    @patch("services.oracle_api.requests.get")
    def test_success_uses_read_only_get(self, get):
        get.return_value = Mock(
            status_code=200, json=Mock(return_value={"items": [], "count": 0})
        )
        result = test_connection(
            "https://demo.fa.us2.oraclecloud.com", "test_user", "test_password"
        )
        self.assertTrue(result.success)
        self.assertEqual(result.po_count_in_response, 0)
        self.assertEqual(get.call_args.kwargs["params"], {"limit": 1})
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertEqual(get.call_args.kwargs["timeout"], (5, 20))
        self.assertEqual(
            get.call_args.args[0],
            "https://demo.fa.us2.oraclecloud.com"
            "/fscmRestApi/resources/11.13.18.05/purchaseOrders",
        )

    @patch("services.oracle_api.requests.get")
    def test_unauthorized_response(self, get):
        get.return_value = Mock(status_code=401)
        result = test_connection(
            "https://demo.fa.us2.oraclecloud.com", "test_user", "wrong_password"
        )
        self.assertFalse(result.success)
        self.assertIn("401", result.message)
        self.assertNotIn("wrong_password", result.message)

    @patch("services.oracle_api.requests.get")
    def test_network_exception(self, get):
        get.side_effect = requests.ConnectionError("Sensitive internal network details")
        result = test_connection(
            "https://demo.fa.us2.oraclecloud.com", "user", "password"
        )
        self.assertFalse(result.success)
        self.assertNotIn("Sensitive", result.message)

    @patch("services.oracle_api.requests.get")
    def test_redirect_is_blocked(self, get):
        get.return_value = Mock(status_code=302)
        result = test_connection(
            "https://demo.fa.us2.oraclecloud.com", "user", "password"
        )
        self.assertFalse(result.success)
        self.assertIn("redirect", result.message.lower())


if __name__ == "__main__":
    unittest.main()
