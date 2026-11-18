# OraFusion Bulk PO Attachment Manager

A Streamlit tool for preparing and validating bulk Purchase Order attachment mappings for Oracle Fusion Cloud Procurement.

## Current status

**Phase 1: Local mapping validation** is ready. **Phase 2: Read-only Oracle connection check and Reference Center** are available via the Oracle Reference Center tab. PO attachment upload, creation of change orders, and submission remain disabled.

## Features

- Upload an XLSX/CSV mapping and a ZIP of attachment files.
- Match each attachment to its exact PO Number and ZIP folder.
- Support multiple different attachments per PO.
- Reject missing paths, mismatched PO folders, duplicate mappings, unsupported extensions, unsafe ZIP entries, and oversized files.
- Preview success/error rows and download an audit-friendly CSV validation report.
- Download an XLSX mapping template.
- Enter Oracle Fusion base instance URL, username, and password, then test the read-only Purchase Orders endpoint.
- Look up up to 20 PO Numbers per request and resolve each to POHeaderId, supplier, status, Procurement BU, and sold-to legal entity. Block ambiguous and missing results; export an audit-friendly CSV.

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

## Oracle connection test

In the **Oracle Reference Center** tab, enter the HTTPS Oracle Fusion instance base URL (for example, `https://example.fa.region.oraclecloud.com`). This version accepts `*.oraclecloud.com` hosts without custom ports or paths. Use an authorized least-privilege integration account and select **Test Connection**. The app executes `GET /fscmRestApi/resources/11.13.18.05/purchaseOrders?limit=1`, checks the response, and displays a success/error message. It does not store credentials in repository files or application logs. Password widget values may remain in the active Streamlit session until it ends.

**Important:** Do not enter Oracle credentials into a publicly accessible Streamlit Community Cloud deployment. Use organization-approved private hosting, access controls, and secrets management before connecting real credentials. HTTP Basic Authentication is an initial testing option; use the organization's approved authentication pattern for production.

## PO Reference Center

Paste PO Numbers (newlines, commas, or semicolons) into the Reference Center and click **Resolve PO References (GET)**. The application queries `purchaseOrders` with the `OrderNumber` filter, verifies an exact match in the response, and displays the `POHeaderId` and business context. The optional Sold-to Legal Entity filter can disambiguate multiple results for the same PO Number. Partial result pages are never automatically confirmed. No reference data is stored in the repo and no PO is changed by the lookup.

**Important:** `POHeaderId` is the internal PO identifier, but the `draftPurchaseOrdersUniqID` placeholder in the attachment POST endpoint is a draft resource identifier. The upload integration must obtain the correct draft resource key or link from Oracle. An approved PO requires a buyer change order before adding attachments. The actual upload endpoint will be `POST /fscmRestApi/resources/11.13.18.05/draftPurchaseOrders/{draftPurchaseOrdersUniqID}/child/attachments`, but it is NOT implemented yet.

## Next phase

Oracle integration will require bulk read-only PO verification, explicit Procurement BU disambiguation, role/privilege checks, approved-PO change order handling, upload verification, a separate submit control, retries, and an audit log. Test against an authorized non-production Oracle Fusion environment first.

## Security

Never commit Oracle credentials, API tokens, supplier documents, or real PO exports to a public repository. Use Streamlit Secrets or environment variables for credentials in future phases. Review deployment access restrictions before working with confidential business attachments.
