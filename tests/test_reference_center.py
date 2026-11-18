import unittest
from unittest.mock import Mock, patch

from services.reference_center import (
    ReferenceLookupError,
    lookup_po_references,
    parse_po_numbers,
)

INSTANCE = "https://example.fa.us2.oraclecloud.com"


class ReferenceCenterTests(unittest.TestCase):
    def test_parse_deduplicates_preserving_leading_zeros(self):
        self.assertEqual(
            parse_po_numbers("0001\n0002;0001,ABC-3"),
            ["0001", "0002", "ABC-3"],
        )

    def test_parse_rejects_query_injection(self):
        with self.assertRaises(ReferenceLookupError):
            parse_po_numbers("1234';OrderNumber=5678")

    @patch("services.reference_center.requests.get")
    def test_exact_match_returns_id(self, get):
        get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "items": [
                        {
                            "OrderNumber": "0001",
                            "POHeaderId": 664294,
                            "Supplier": "Demo",
                            "ProcurementBU": "Operations",
                            "SoldToLegalEntity": "LE1",
                            "Status": "Open",
                        }
                    ],
                    "hasMore": False,
                }
            ),
        )
        result = lookup_po_references(INSTANCE, "user", "pass", ["0001"])
        self.assertEqual(result[0]["POHeaderId"], 664294)
        self.assertEqual(result[0]["LookupStatus"], "MATCHED")
        self.assertEqual(get.call_args.kwargs["params"]["q"], "OrderNumber='0001'")
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    @patch("services.reference_center.requests.get")
    def test_ambiguity_prevents_auto_matching(self, get):
        get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "items": [
                        {"OrderNumber": "100", "POHeaderId": 10, "SoldToLegalEntity": "LE1"},
                        {"OrderNumber": "100", "POHeaderId": 11, "SoldToLegalEntity": "LE2"},
                    ],
                    "hasMore": False,
                }
            ),
        )
        result = lookup_po_references(INSTANCE, "user", "pass", ["100"])
        self.assertEqual(len(result), 2)
        self.assertTrue(all(row["LookupStatus"] == "AMBIGUOUS" for row in result))

    @patch("services.reference_center.requests.get")
    def test_legal_entity_resolves_ambiguity(self, get):
        get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "items": [
                        {"OrderNumber": "100", "POHeaderId": 10, "SoldToLegalEntity": "LE1"},
                        {"OrderNumber": "100", "POHeaderId": 11, "SoldToLegalEntity": "LE2"},
                    ],
                    "hasMore": False,
                }
            ),
        )
        result = lookup_po_references(
            INSTANCE, "user", "pass", ["100"], sold_to_legal_entity="LE2"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["POHeaderId"], 11)
        self.assertEqual(result[0]["LookupStatus"], "MATCHED")

    @patch("services.reference_center.requests.get")
    def test_query_result_is_exact_even_if_server_returns_other_po(self, get):
        get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "items": [{"OrderNumber": "other", "POHeaderId": 99}],
                    "hasMore": False,
                }
            ),
        )
        result = lookup_po_references(INSTANCE, "user", "pass", ["0001"])
        self.assertEqual(result[0]["LookupStatus"], "NOT_FOUND")

    @patch("services.reference_center.requests.get")
    def test_has_more_does_not_confirm_unique(self, get):
        get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "items": [{"OrderNumber": "100", "POHeaderId": 10}],
                    "hasMore": True,
                }
            ),
        )
        result = lookup_po_references(INSTANCE, "user", "pass", ["100"])
        self.assertEqual(result[0]["LookupStatus"], "AMBIGUOUS")

    @patch("services.reference_center.requests.get")
    def test_access_denied_does_not_expose_response(self, get):
        get.return_value = Mock(status_code=403, text="internal secret")
        result = lookup_po_references(INSTANCE, "user", "pass", ["100"])
        self.assertEqual(result[0]["LookupStatus"], "API_ERROR")
        self.assertNotIn("internal secret", result[0]["Message"])


if __name__ == "__main__":
    unittest.main()
