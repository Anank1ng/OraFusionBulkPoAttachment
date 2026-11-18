import pandas as pd
import streamlit as st

from services.oracle_api import InstanceUrlError, test_connection
from utils.mapping_validator import MAX_FILES, MAX_FILE_MB, ValidationError, validate_bundle
from utils.template_builder import build_template

st.set_page_config(
    page_title="OraFusion | Bulk PO Attachment",
    page_icon="📎",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1250px;}
    div[data-testid="stMetric"] {
        border: 1px solid rgba(120, 130, 140, 0.22);
        padding: 14px 16px;
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("📎 OraFusion")
    st.caption("Bulk PO Attachment Manager")
    st.divider()
    st.subheader("Development status")
    st.success("Phase 1: Mapping validator")
    st.info("Phase 2: Read-only Oracle connection test is available.")
    st.markdown("**Validation rules**")
    st.write("• Every file belongs to its mapped PO")
    st.write("• Folder name must match PO Number")
    st.write("• Exact, case-sensitive file paths")
    st.write("• Duplicate and unsafe files are rejected")
    st.divider()
    st.caption("Connection test reads at most one PO. Attachment uploads remain disabled.")

st.title("Bulk Purchase Order Attachment")
st.write(
    "Prepare your PO-to-attachment mapping, inspect all matches, "
    "and catch mistakes before enabling Oracle REST API integration."
)

connection_tab, upload_tab, guide_tab = st.tabs(
    ["🔌 Oracle Connection", "📤 Validate Excel + ZIP", "📘 How it works"]
)

with connection_tab:
    st.subheader("Oracle Fusion Cloud instance")
    st.write(
        "Enter your Oracle Fusion base URL and credentials to test read-only "
        "access to the Purchase Orders REST API."
    )
    st.warning(
        "Security: do not enter personal or production credentials into a "
        "publicly accessible deployment. Use an approved private environment "
        "and a dedicated least-privilege integration account."
    )

    with st.form("oracle_connection_form"):
        instance_url = st.text_input(
            "Instance URL",
            placeholder="https://example.fa.region.oraclecloud.com",
            help=(
                "Use the Oracle Fusion HTTPS base URL only. "
                "This version accepts subdomains of oraclecloud.com."
            ),
        )
        username = st.text_input(
            "Oracle Fusion Username",
            placeholder="Integration account username",
        )
        password = st.text_input(
            "Oracle Fusion Password",
            type="password",
            help="Only used for this read-only connection request. Never commit credentials.",
        )
        acknowledged = st.checkbox(
            "I am testing from an approved, access-controlled deployment."
        )
        submitted = st.form_submit_button(
            "🔌 Test Connection (GET only)", use_container_width=True
        )

    if submitted:
        if not acknowledged:
            st.error("Confirm you are using an approved private environment before testing.")
        else:
            try:
                result = test_connection(instance_url, username, password)
            except InstanceUrlError as exc:
                st.error(str(exc))
            else:
                if result.success:
                    st.success(result.message)
                    st.caption(
                        f"Instance: {result.host} · "
                        f"Items returned: {result.po_count_in_response} "
                        "(limit=1, not total PO count)"
                    )
                else:
                    st.error(result.message)

    st.info(
        "This test performs GET /fscmRestApi/resources/"
        "11.13.18.05/purchaseOrders?limit=1. "
        "It does not change any PO or send uploaded documents."
    )


with upload_tab:
    st.subheader("1. Download the mapping template")
    st.caption(
        "The required columns are PO_Number and File_Path. "
        "Use PO_Number as the first directory in the ZIP file."
    )
    st.download_button(
        "⬇️ Download Excel Template",
        data=build_template(),
        file_name="PO_Attachment_Mapping_Template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )

    st.subheader("2. Upload your mapping and ZIP")
    col_excel, col_zip = st.columns(2)
    with col_excel:
        mapping_file = st.file_uploader(
            "Excel or CSV mapping",
            type=["xlsx", "csv"],
            help="Use the downloaded template to avoid column-name mistakes.",
        )
    with col_zip:
        zip_file = st.file_uploader(
            "ZIP containing attachments",
            type=["zip"],
            help="Example: 100001/Quotation_A.pdf, 100002/Invoice_B.pdf",
        )

    st.subheader("3. Preview validation results")
    if mapping_file is None or zip_file is None:
        st.info("Upload both files to begin validation. Nothing will be sent to Oracle.")
    else:
        try:
            report = validate_bundle(
                mapping_file.getvalue(),
                mapping_file.name,
                zip_file.getvalue(),
            )
        except (ValidationError, ValueError, OSError, pd.errors.ParserError) as exc:
            st.error(str(exc))
        else:
            total, valid, invalid, po_count = report.summary()
            a, b, c, d = st.columns(4)
            a.metric("Mapping rows", total)
            b.metric("Matched", valid)
            c.metric("Errors", invalid)
            d.metric("Unique POs", po_count)

            if report.has_errors:
                st.error(
                    "Validation failed for one or more rows. "
                    "Correct every error before proceeding."
                )
            else:
                st.success(
                    "All mapped files passed local validation. "
                    "This is not confirmation that any PO exists in Oracle."
                )

            if report.warnings:
                with st.expander(
                    f"⚠️ ZIP warnings ({len(report.warnings)})", expanded=True
                ):
                    for warning in report.warnings[:25]:
                        st.warning(warning)
                    if len(report.warnings) > 25:
                        st.caption("Download the report or clean up extra ZIP entries.")

            st.dataframe(
                report.rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "PO_Number": "PO Number",
                    "File_Path": "Attachment path",
                    "Category": "Category",
                    "Description": "Description",
                    "Status": "Validation status",
                    "Message": "Details",
                    "Size_KB": st.column_config.NumberColumn(
                        "Size (KB)", format="%.1f"
                    ),
                },
            )

            st.download_button(
                "⬇️ Download Validation Report (CSV)",
                data=report.csv_bytes(),
                file_name="PO_Attachment_Validation_Report.csv",
                mime="text/csv",
            )

            st.divider()
            st.subheader("4. Oracle upload")
            st.info(
                "Actual PO lookup, attachment upload, and change-order submission "
                "are intentionally disabled in Phase 1. "
                "No Oracle record has been created or modified."
            )
            st.button("Upload to Oracle Fusion", disabled=True)

with guide_tab:
    st.subheader("Required Excel columns")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "PO_Number": "100001",
                    "File_Path": "100001/Attachment_A.pdf",
                    "Category": "MISC",
                    "Description": "Quotation for PO A",
                },
                {
                    "PO_Number": "100002",
                    "File_Path": "100002/Attachment_B.pdf",
                    "Category": "MISC",
                    "Description": "Quotation for PO B",
                },
                {
                    "PO_Number": "100002",
                    "File_Path": "100002/Attachment_C.pdf",
                    "Category": "MISC",
                    "Description": "Specifications for PO B",
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Example ZIP layout")
    st.code(
        "PO_Attachments.zip\n"
        "├── 100001/\n"
        "│   └── Attachment_A.pdf\n"
        "└── 100002/\n"
        "    ├── Attachment_B.pdf\n"
        "    └── Attachment_C.pdf",
        language="text",
    )
    st.subheader("Safety and validation")
    st.write(
        "The mapping is explicit: the app never guesses a PO based on filename. "
        "PO_Number must match the first ZIP folder exactly. "
        "The ZIP path must also match File_Path exactly."
    )
    st.write(
        f"Current MVP limits: up to {MAX_FILES} ZIP files, "
        f"{MAX_FILE_MB} MB per file. "
        "Wrong paths, duplicate mappings, risky ZIP entries, "
        "and missing files produce validation errors."
    )
    st.warning(
        "Phase 1 validates only the mapping and ZIP. "
        "It does not verify PO existence, supplier, Procurement BU, "
        "change-order status, or Oracle attachment permissions."
    )
