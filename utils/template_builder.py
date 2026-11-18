from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill


COLUMNS = [
    "PO_Number",
    "SoldToLegalEntity",
    "File_Path",
    "CategoryName",
    "Title",
    "Description",
    "ContentRepositoryFileShared",
]


def build_template() -> bytes:
    frame = pd.DataFrame(
        [
            {
                "PO_Number": "100001",
                "SoldToLegalEntity": "Vision Operations",
                "File_Path": "100001/Attachment_A.pdf",
                "CategoryName": "MISC",
                "Title": "Quotation for PO A",
                "Description": "Supporting quotation",
                "ContentRepositoryFileShared": "false",
            },
            {
                "PO_Number": "100002",
                "SoldToLegalEntity": "Vision Operations",
                "File_Path": "100002/Attachment_B.pdf",
                "CategoryName": "MISC",
                "Title": "Specification for PO B",
                "Description": "Technical specification",
                "ContentRepositoryFileShared": "false",
            },
        ],
        columns=COLUMNS,
    )
    guide = pd.DataFrame(
        [
            ["PO_Number", "Required", "Readable PO number. POHeaderId will be retrieved from Oracle."],
            ["SoldToLegalEntity", "Optional", "Use exact Oracle name if the PO number is not unique."],
            ["File_Path", "Required", "Exact ZIP path: <PO_Number>/<file name>."],
            ["CategoryName", "Optional", "Oracle attachment category, for example MISC. Confirm the category in your environment."],
            ["Title", "Optional", "Oracle attachment Title; defaults to the file name."],
            ["Description", "Optional", "Oracle attachment Description (up to 255 characters)."],
            ["ContentRepositoryFileShared", "Optional", "true or false; defaults to false."],
            ["Generated: DatatypeCode", "Automatic", "Always FILE in this version."],
            ["Generated: FileName", "Automatic", "Read from File_Path."],
            ["Generated: UploadedFileContentType", "Automatic", "Derived from the file extension."],
            ["Generated: FileContents", "Automatic", "Base64-encoded from the file in ZIP only when uploading."],
            ["POHeaderId / draft resource key", "Automatic", "Resolved from Oracle. Never guess or manually type an ID."],
            ["Approved PO", "Workflow", "Buyer change order is required before attachment POST."],
            ["Important", "Security", "Do not include real supplier documents in the public repository."],
        ],
        columns=["Field", "Input", "Meaning"],
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Mapping", index=False)
        guide.to_excel(writer, sheet_name="Guide", index=False)
        for sheet in writer.sheets.values():
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            sheet.row_dimensions[1].height = 28
            for cell in sheet[1]:
                cell.fill = PatternFill("solid", fgColor="193E69")
                cell.font = Font(name="Aptos", size=11, color="FFFFFF", bold=True)
                cell.alignment = Alignment(vertical="center")
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    cell.font = Font(name="Aptos", size=10)
                    cell.alignment = Alignment(vertical="center", wrap_text=True)
        sheet = writer.sheets["Mapping"]
        for column, width in {
            "A": 20, "B": 28, "C": 46, "D": 20,
            "E": 35, "F": 43, "G": 30,
        }.items():
            sheet.column_dimensions[column].width = width
        for row in range(2, 500):
            sheet[f"A{row}"].number_format = "@"
        guide_sheet = writer.sheets["Guide"]
        for column, width in {"A": 36, "B": 16, "C": 88}.items():
            guide_sheet.column_dimensions[column].width = width
    return output.getvalue()
