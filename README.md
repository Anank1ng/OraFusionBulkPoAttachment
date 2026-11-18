# OraFusion Bulk PO Attachment Manager

A Streamlit tool for preparing and validating bulk Purchase Order attachment mappings for Oracle Fusion Cloud Procurement.

## Phase 1 status

**Local validation only (dry run).** This version does not connect to Oracle Fusion, create change orders, or upload attachments. Oracle REST API integration is a separate development phase.

## Features

- Upload an XLSX/CSV mapping and a ZIP of attachment files.
- Match each attachment to its exact PO Number and ZIP folder.
- Support multiple different attachments per PO.
- Reject missing paths, mismatched PO folders, duplicate mappings, unsupported extensions, unsafe ZIP entries, and oversized files.
- Preview success/error rows and download an audit-friendly CSV validation report.
- Download an XLSX mapping template.

## Setup

1. Install Python 3.11+.
2. Install dependencies: `pip install -r requirements.txt`
3. Start the app: `streamlit run Main.py`

For Streamlit Community Cloud, select the repository's `main` branch and use `Main.py` as the entrypoint.

## Excel template

| PO_Number | File_Path | Category | Description |
|---|---|---|---|
| 100001 | 100001/Attachment_A.pdf | MISC | Quotation for PO A |
| 100002 | 100002/Attachment_B.pdf | MISC | Quotation for PO B |

PO_Number and File_Path are required. Category and Description are optional. PO numbers are treated as text, preserving leading zeros. Exact file matching is case-sensitive. Each mapped file must appear under the matching PO folder.

Example ZIP:

```text
PO_Attachments.zip
├── 100001/
│   └── Attachment_A.pdf
└── 100002/
    └── Attachment_B.pdf
```

The ZIP must contain the mapped attachment files. Put the spreadsheet in a separate upload input; it does not have to be inside the ZIP.

## Running tests

`python -m unittest discover -s tests -v`

## Next phase

Oracle integration will require read-only PO verification, explicit Procurement BU disambiguation, role/privilege checks, approved-PO change order handling, upload verification, a separate submit control, retries, and an audit log. Test against an authorized non-production Oracle Fusion environment first.

## Security

Never commit Oracle credentials, API tokens, supplier documents, or real PO exports to a public repository. Use Streamlit Secrets or environment variables for credentials in future phases. Review deployment access restrictions before working with confidential business attachments.
