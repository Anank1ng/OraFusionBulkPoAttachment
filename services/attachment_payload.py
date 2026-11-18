import base64
import mimetypes
from pathlib import PurePosixPath


def build_attachment_payload(row: dict, file_bytes: bytes) -> dict:
    if row.get("Status") != "MATCHED":
        raise ValueError("Only validated attachment mappings can generate payloads.")
    if not file_bytes:
        raise ValueError("Attachment contents cannot be empty.")
    file_path = str(row["File_Path"])
    filename = PurePosixPath(file_path).name
    category = str(row.get("CategoryName") or "MISC")
    if not filename or not category:
        raise ValueError("FileName and CategoryName are required.")
    shared = str(row.get("ContentRepositoryFileShared") or "false").lower()
    if shared not in ("true", "false"):
        raise ValueError("ContentRepositoryFileShared must be true or false.")
    return {
        "DatatypeCode": "FILE",
        "FileName": filename,
        "CategoryName": category,
        "UploadedFileContentType": (
            mimetypes.guess_type(filename)[0] or "application/octet-stream"
        ),
        "ContentRepositoryFileShared": shared == "true",
        "Title": str(row.get("Title") or filename),
        "Description": str(row.get("Description") or ""),
        "FileContents": base64.b64encode(file_bytes).decode("ascii"),
    }
