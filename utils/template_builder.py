from io import BytesIO

import pandas as pd


def build_template() -> bytes:
    frame = pd.DataFrame(
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
        ]
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Mapping", index=False)
        sheet = writer.sheets["Mapping"]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column, width in {"A": 20, "B": 42, "C": 18, "D": 45}.items():
            sheet.column_dimensions[column].width = width
    return output.getvalue()
