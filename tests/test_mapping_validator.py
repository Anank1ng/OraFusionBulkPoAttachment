import unittest
from io import BytesIO
from zipfile import ZipFile

import pandas as pd

from utils.mapping_validator import ValidationError, validate_bundle


def make_mapping(rows):
    buffer = BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


def make_zip(entries):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class MappingValidationTests(unittest.TestCase):
    def test_exact_po_attachment_mapping(self):
        mapping = make_mapping([
            {"PO_Number": "0001", "File_Path": "0001/A.pdf"},
            {"PO_Number": "0002", "File_Path": "0002/B.pdf"},
        ])
        archive = make_zip({"0001/A.pdf": b"A", "0002/B.pdf": b"B"})
        report = validate_bundle(mapping, "mapping.xlsx", archive)
        self.assertEqual(report.summary(), (2, 2, 0, 2))
        self.assertFalse(report.has_errors)

    def test_wrong_po_folder_is_rejected(self):
        mapping = make_mapping([
            {"PO_Number": "100001", "File_Path": "100002/A.pdf"},
        ])
        report = validate_bundle(
            mapping, "mapping.xlsx", make_zip({"100002/A.pdf": b"A"})
        )
        self.assertTrue(report.has_errors)
        self.assertIn("does not match", report.rows.iloc[0]["Message"])

    def test_missing_file_is_rejected(self):
        mapping = make_mapping([
            {"PO_Number": "100001", "File_Path": "100001/A.pdf"}
        ])
        report = validate_bundle(
            mapping, "mapping.xlsx", make_zip({"100001/B.pdf": b"B"})
        )
        self.assertTrue(report.has_errors)
        self.assertTrue(report.warnings)

    def test_duplicate_mapping_is_rejected(self):
        mapping = make_mapping([
            {"PO_Number": "100001", "File_Path": "100001/A.pdf"},
            {"PO_Number": "100001", "File_Path": "100001/A.pdf"},
        ])
        report = validate_bundle(
            mapping, "mapping.xlsx", make_zip({"100001/A.pdf": b"A"})
        )
        self.assertEqual(report.summary()[2], 2)

    def test_zip_traversal_is_blocked(self):
        mapping = make_mapping([
            {"PO_Number": "100001", "File_Path": "100001/A.pdf"},
        ])
        with self.assertRaises(ValidationError):
            validate_bundle(
                mapping, "mapping.xlsx", make_zip({"../unsafe.pdf": b"A"})
            )

    def test_unmapped_file_is_reported(self):
        mapping = make_mapping([
            {"PO_Number": "100001", "File_Path": "100001/A.pdf"}
        ])
        report = validate_bundle(
            mapping,
            "mapping.xlsx",
            make_zip({"100001/A.pdf": b"A", "100002/Extra.pdf": b"B"}),
        )
        self.assertFalse(report.has_errors)
        self.assertEqual(len(report.warnings), 1)


if __name__ == "__main__":
    unittest.main()
