from dataclasses import dataclass
from io import BytesIO
import mimetypes
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

import pandas as pd

MAX_FILES = 500
MAX_ROWS = 2000
MAX_FILE_MB = 25
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024
MAX_TOTAL_BYTES = 400 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx",
    ".xls", ".xlsx", ".txt", ".csv", ".ppt", ".pptx",
}
REQUIRED_COLUMNS = ("PO_Number", "File_Path")
OPTIONAL_COLUMNS = ("SoldToLegalEntity", "CategoryName", "Title", "Description", "ContentRepositoryFileShared")
DISPLAY_COLUMNS = (
    "PO_Number", "SoldToLegalEntity", "File_Path", "CategoryName",
    "Title", "Description", "ContentRepositoryFileShared",
    "DatatypeCode", "FileName", "UploadedFileContentType",
    "Status", "Message", "Size_KB",
)


class ValidationError(Exception):
    pass


@dataclass
class ValidationReport:
    rows: pd.DataFrame
    warnings: list[str]

    @property
    def has_errors(self) -> bool:
        return bool((self.rows["Status"] == "ERROR").any())

    def summary(self) -> tuple[int, int, int, int]:
        total = len(self.rows)
        valid = int((self.rows["Status"] == "MATCHED").sum())
        invalid = total - valid
        po_count = self.rows["PO_Number"].loc[
            self.rows["PO_Number"].ne("")
        ].nunique()
        return total, valid, invalid, int(po_count)

    def csv_bytes(self) -> bytes:
        safe = self.rows.copy()
        for column in safe.columns:
            if safe[column].dtype == "object":
                safe[column] = safe[column].map(
                    lambda value: "'" + value
                    if isinstance(value, str)
                    and value.lstrip().startswith(("=", "+", "-", "@"))
                    else value
                )
        return safe.to_csv(index=False).encode("utf-8-sig")


def _read_mapping(content: bytes, filename: str) -> pd.DataFrame:
    if not content:
        raise ValidationError("The mapping file is empty.")
    extension = PurePosixPath(filename.lower()).suffix
    try:
        if extension == ".xlsx":
            dataframe = pd.read_excel(
                BytesIO(content),
                engine="openpyxl",
                dtype=str,
                keep_default_na=False,
            )
        elif extension == ".csv":
            dataframe = pd.read_csv(
                BytesIO(content),
                dtype=str,
                keep_default_na=False,
                encoding="utf-8-sig",
                sep=None,
                engine="python",
            )
        else:
            raise ValidationError("Only XLSX and CSV mapping files are supported.")
    except (ValueError, BadZipFile, UnicodeError) as exc:
        raise ValidationError(f"Cannot read mapping file: {exc}") from exc

    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    if dataframe.columns.duplicated().any():
        raise ValidationError("The mapping contains duplicate column headers.")
    missing = [column for column in REQUIRED_COLUMNS if column not in dataframe]
    if missing:
        raise ValidationError(
            "Missing required columns: " + ", ".join(missing)
        )
    if dataframe.empty:
        raise ValidationError("The mapping does not contain any rows.")
    if len(dataframe) > MAX_ROWS:
        raise ValidationError(
            f"Mapping has more than the {MAX_ROWS} supported rows."
        )

    if "CategoryName" not in dataframe and "Category" in dataframe:
        dataframe["CategoryName"] = dataframe["Category"]
    for column in OPTIONAL_COLUMNS:
        if column not in dataframe:
            dataframe[column] = ""
    columns = list(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    dataframe = dataframe[columns].fillna("").astype(str)
    for column in columns:
        dataframe[column] = dataframe[column].str.strip()
    dataframe["CategoryName"] = dataframe["CategoryName"].mask(
        dataframe["CategoryName"].eq(""), "MISC"
    )
    dataframe["ContentRepositoryFileShared"] = dataframe[
        "ContentRepositoryFileShared"
    ].mask(dataframe["ContentRepositoryFileShared"].eq(""), "false")
    return dataframe


def _check_zip_path(path: str) -> bool:
    if not path or "\\" in path or path.startswith("/"):
        return False
    if any(part in ("", ".", "..") for part in path.split("/")):
        return False
    if ":" in path.split("/")[0]:
        return False
    return True


def _load_zip_index(content: bytes) -> tuple[dict, list[str]]:
    if not content:
        raise ValidationError("The ZIP file is empty.")
    try:
        archive = ZipFile(BytesIO(content))
    except BadZipFile as exc:
        raise ValidationError("Cannot open ZIP: invalid or damaged archive.") from exc

    index = {}
    warnings = []
    total = 0
    with archive:
        for info in archive.infolist():
            name = info.filename
            if name.startswith("__MACOSX/") or name == ".DS_Store":
                continue
            if info.is_dir():
                continue
            if not _check_zip_path(name):
                raise ValidationError(f"Unsafe ZIP path detected: {name}")
            if info.flag_bits & 0x1:
                raise ValidationError(f"Encrypted ZIP entry not supported: {name}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValidationError(f"Symlinks are not permitted in ZIP: {name}")
            if name in index:
                raise ValidationError(f"Duplicate ZIP path detected: {name}")

            total += info.file_size
            if info.file_size > MAX_FILE_BYTES:
                raise ValidationError(
                    f"ZIP entry exceeds {MAX_FILE_MB} MB: {name}"
                )
            if total > MAX_TOTAL_BYTES:
                raise ValidationError(
                    "ZIP uncompressed size exceeds the 400 MB safety limit."
                )
            if info.compress_size == 0 and info.file_size > 0:
                raise ValidationError(f"Suspicious ZIP entry size: {name}")
            if (
                info.compress_size > 0
                and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise ValidationError(f"Suspicious ZIP compression ratio: {name}")
            index[name] = info

    if not index:
        raise ValidationError("The ZIP does not contain any usable attachment files.")
    if len(index) > MAX_FILES:
        raise ValidationError(f"ZIP has more than {MAX_FILES} attachment files.")
    return index, warnings


def validate_bundle(
    mapping_content: bytes,
    mapping_filename: str,
    zip_content: bytes,
) -> ValidationReport:
    mapping = _read_mapping(mapping_content, mapping_filename)
    zip_index, warnings = _load_zip_index(zip_content)
    path_counts = mapping["File_Path"].value_counts()
    records = []
    mapped_paths = set()

    for _, item in mapping.iterrows():
        po_number = item["PO_Number"]
        file_path = item["File_Path"]
        legal_entity = item["SoldToLegalEntity"]
        category = item["CategoryName"]
        title = item["Title"] or PurePosixPath(file_path).name
        description = item["Description"]
        shared = item["ContentRepositoryFileShared"].lower()
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        messages = []
        size_kb = None

        if len(category) > 30:
            messages.append("CategoryName must be 30 characters or fewer.")
        if len(description) > 255:
            messages.append("Description must be 255 characters or fewer.")
        if shared not in {"true", "false"}:
            messages.append("ContentRepositoryFileShared must be true or false.")
        if not po_number:
            messages.append("PO_Number is required.")
        elif "/" in po_number or "\\" in po_number or po_number in (".", ".."):
            messages.append("PO_Number cannot contain path separators.")
        if not file_path:
            messages.append("File_Path is required.")
        elif not _check_zip_path(file_path):
            messages.append("File_Path is not a safe relative ZIP path.")
        else:
            parts = PurePosixPath(file_path).parts
            if len(parts) < 2:
                messages.append("File_Path must include a PO folder.")
            elif po_number and parts[0] != po_number:
                messages.append(
                    f"PO folder '{parts[0]}' does not match PO_Number '{po_number}'."
                )
            if PurePosixPath(file_path).suffix.lower() not in ALLOWED_EXTENSIONS:
                messages.append("Attachment file extension is not supported.")
            if path_counts[file_path] > 1:
                messages.append("Duplicate File_Path in Excel mapping.")
            if file_path not in zip_index:
                messages.append("Exact file path was not found in ZIP.")
            else:
                info = zip_index[file_path]
                size_kb = round(info.file_size / 1024, 1)
                if info.file_size == 0:
                    messages.append("Attachment is empty.")
                mapped_paths.add(file_path)

        records.append(
            {
                "PO_Number": po_number,
                "SoldToLegalEntity": legal_entity,
                "File_Path": file_path,
                "CategoryName": category,
                "Title": title,
                "Description": description,
                "ContentRepositoryFileShared": shared,
                "DatatypeCode": "FILE",
                "FileName": PurePosixPath(file_path).name,
                "UploadedFileContentType": mime_type,
                "Status": "ERROR" if messages else "MATCHED",
                "Message": " ".join(messages) if messages else "Exact mapping validated.",
                "Size_KB": size_kb,
            }
        )

    unused = sorted(set(zip_index) - mapped_paths)
    if unused:
        preview = ", ".join(unused[:10])
        if len(unused) > 10:
            preview += f" (and {len(unused) - 10} more)"
        warnings.append(
            f"{len(unused)} ZIP file(s) are not referenced by the mapping: {preview}"
        )
    return ValidationReport(
        rows=pd.DataFrame.from_records(records, columns=DISPLAY_COLUMNS),
        warnings=warnings,
    )
