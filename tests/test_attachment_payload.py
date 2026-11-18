import base64
import unittest

from services.attachment_payload import build_attachment_payload


class AttachmentPayloadTests(unittest.TestCase):
    def test_payload_matches_oracle_attachment_fields(self):
        row = {
            "Status": "MATCHED",
            "File_Path": "100001/Quotation.pdf",
            "CategoryName": "MISC",
            "Title": "Quotation",
            "Description": "Supplier quotation",
            "ContentRepositoryFileShared": "false",
        }
        payload = build_attachment_payload(row, b"example attachment")
        self.assertEqual(payload["DatatypeCode"], "FILE")
        self.assertEqual(payload["FileName"], "Quotation.pdf")
        self.assertEqual(payload["UploadedFileContentType"], "application/pdf")
        self.assertFalse(payload["ContentRepositoryFileShared"])
        self.assertEqual(
            base64.b64decode(payload["FileContents"]), b"example attachment"
        )
        self.assertNotIn("POHeaderId", payload)
        self.assertNotIn("OrderNumber", payload)

    def test_unvalidated_row_is_rejected(self):
        with self.assertRaises(ValueError):
            build_attachment_payload(
                {"Status": "ERROR", "File_Path": "100001/Test.pdf"}, b"content"
            )

    def test_empty_file_is_rejected(self):
        with self.assertRaises(ValueError):
            build_attachment_payload(
                {"Status": "MATCHED", "File_Path": "100001/Test.pdf"}, b""
            )


if __name__ == "__main__":
    unittest.main()
