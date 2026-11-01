"""Parse and validate bulk gift-order CSV uploads."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email

from .config import GIFT_CATALOG, settings
from .shipping_address import ShippingAddressParts, parts_from_optional, shipping_address_values

# Headers accepted (case-insensitive). Address pieces and Comment are optional per row.
REQUIRED_HEADERS = ("name", "email", "cookies")
OPTIONAL_HEADERS = (
    "comment",
    "company",
    "street",
    "street2",
    "city",
    "state",
    "postal_code",
    "address",
)
ALL_HEADERS = REQUIRED_HEADERS + OPTIONAL_HEADERS

COOKIE_COUNT_TO_GIFT_ID: dict[int, str] = {
    int(item["cookie_count"]): str(item["id"]) for item in GIFT_CATALOG
}
ALLOWED_COOKIE_COUNTS = frozenset(COOKIE_COUNT_TO_GIFT_ID)

# Title row above the header. Import already skips a line that is not the header.
# No commas, so this stays one cell and is not read as column names.
CSV_TEMPLATE_NOTE = (
    "Keep these column names. Put 4 or 12 under Cookies. "
    "Do not rename that column to Number of Cookies (4 or 12). "
    "Comment is optional; leave it blank for the default gift note.\n"
)
CSV_TEMPLATE_HEADERS = (
    "Name,Email,Cookies,Company,Street,Street2,City,State,Postal Code,Comment\n"
)

# Filled example rows so users can see both known-address and request-address cases.
CSV_EXAMPLE_BODY = (
    "Jane Smith,jane@example.com,4,,123 Main St,,Springfield,IL,62704,Thanks for the great meeting!\n"
    "Bob Jones,bob@example.com,12,,,,,,,\n"
    "Casey NoEmail,,4,,,,,,,\n"
    "Alex Rivera,alex@example.com,12,Acme Tower,456 Oak Ave,Apt 2,Austin,TX,78701,\n"
)

DEFAULT_IMPORT_NOTE = "Enjoy these cookies — a small thank-you from us."
NOTE_MAX_LENGTH = 1000

_HEADER_ALIASES: dict[str, str] = {
    "name": "name",
    "full name": "name",
    "recipient_name": "name",
    "recipient name": "name",
    "email": "email",
    "e-mail": "email",
    "email address": "email",
    "recipient_email": "email",
    "recipient email": "email",
    "cookies": "cookies",
    "cookie": "cookies",
    "cookie_count": "cookies",
    "cookie count": "cookies",
    "number of cookies": "cookies",
    "comment": "comment",
    "comments": "comment",
    "note": "comment",
    "notes": "comment",
    "gift_note": "comment",
    "gift note": "comment",
    "gift_message": "comment",
    "gift message": "comment",
    "message": "comment",
    "address": "address",
    "shipping_address": "address",
    "shipping address": "address",
    "company": "company",
    "company_name": "company",
    "company name": "company",
    "shipping_company": "company",
    "street": "street",
    "street1": "street",
    "street 1": "street",
    "shipping_street": "street",
    "address1": "street",
    "address 1": "street",
    "street2": "street2",
    "street 2": "street2",
    "shipping_street2": "street2",
    "address2": "street2",
    "address 2": "street2",
    "apt": "street2",
    "suite": "street2",
    "city": "city",
    "shipping_city": "city",
    "state": "state",
    "shipping_state": "state",
    "province": "state",
    "postal_code": "postal_code",
    "postal code": "postal_code",
    "zip": "postal_code",
    "zip_code": "postal_code",
    "zip code": "postal_code",
    "zipcode": "postal_code",
    "shipping_postal_code": "postal_code",
}

_EXCEL_SAVE_AS = (
    "In Excel choose File → Save As and pick CSV UTF-8 (Comma delimited) (*.csv). "
    "Older Excel lists this as CSV (Comma delimited) (*.csv)."
)
_SHEETS_DOWNLOAD = (
    "In Google Sheets choose File → Download → Comma-separated values (.csv)."
)

_EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xls", ".numbers", ".ods")
_OLE_WORKBOOK_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_HEADER_SCAN_LIMIT = 20
_DELIMITERS = (",", ";", "\t")


@dataclass(frozen=True)
class ParsedOrderRow:
    row_number: int  # 1-based data row (header is row 1)
    recipient_name: str
    recipient_email: str | None
    gift_id: str
    cookie_count: int
    note: str
    shipping_address: str | None
    address_parts: ShippingAddressParts | None
    request_recipient_address: bool


@dataclass(frozen=True)
class RowError:
    row: int
    message: str


def template_csv() -> str:
    """Reminder line plus the header row. No sample orders."""
    return CSV_TEMPLATE_NOTE + CSV_TEMPLATE_HEADERS


def example_csv() -> str:
    """Downloadable example with a reminder, headers, and sample rows."""
    return CSV_TEMPLATE_NOTE + CSV_TEMPLATE_HEADERS + CSV_EXAMPLE_BODY


def workbook_upload_message(filename: str) -> str:
    """Tell the person how to save a real CSV from the app that made this file."""
    name = (filename or "").strip().lower()
    if name.endswith(".numbers"):
        return (
            "This is an Apple Numbers spreadsheet, not a CSV. "
            "In Numbers choose File → Export To → CSV, then upload that file."
        )
    if name.endswith(".ods"):
        return (
            "This is a spreadsheet workbook (.ods), not a CSV. "
            "Save it as Text CSV (.csv), then upload that file. "
            f"{_EXCEL_SAVE_AS} {_SHEETS_DOWNLOAD}"
        )
    if name.endswith(".csv"):
        return (
            "This file is named .csv, but it is still an Excel or Google Sheets workbook. "
            "Renaming the file does not convert it. "
            f"{_EXCEL_SAVE_AS} {_SHEETS_DOWNLOAD}"
        )
    extension = next(
        (suffix for suffix in (".xlsx", ".xlsm", ".xls") if name.endswith(suffix)),
        "",
    )
    labeled = f" ({extension})" if extension else ""
    return (
        f"This is an Excel workbook{labeled}, not a CSV. "
        "Upload the .csv you save, not the workbook. "
        f"{_EXCEL_SAVE_AS} {_SHEETS_DOWNLOAD}"
    )


def non_csv_upload_message() -> str:
    """Used when the upload is not a .csv and is not a known workbook."""
    return f"Please upload a .csv file. {_EXCEL_SAVE_AS} {_SHEETS_DOWNLOAD}"


def looks_like_excel_workbook(filename: str, raw: bytes) -> bool:
    """True for .xlsx/.xls uploads, including workbooks renamed to .csv."""
    name = (filename or "").strip().lower()
    if name.endswith(_EXCEL_EXTENSIONS):
        return True
    return raw.startswith(b"PK\x03\x04") or raw.startswith(_OLE_WORKBOOK_MAGIC)


def _strip_format_chars(raw: str) -> str:
    """Drop BOM / zero-width characters Sheets and Excel sometimes leave in cells."""
    cleaned = "".join(ch for ch in raw if unicodedata.category(ch) != "Cf")
    return cleaned.replace("\u00a0", " ")


def _clean_cell(value: str) -> str:
    return _strip_format_chars(value).strip()


def _normalize_header(raw: str) -> str | None:
    spaced = re.sub(r"\s+", " ", _strip_format_chars(raw).strip().lower().replace("_", " "))
    underscored = spaced.replace(" ", "_")
    return _HEADER_ALIASES.get(spaced) or _HEADER_ALIASES.get(underscored)


def _header_map_from_cells(cells: list[str]) -> dict[str, int]:
    header_map: dict[str, int] = {}
    for index, cell in enumerate(cells):
        normalized = _normalize_header(cell)
        if normalized and normalized not in header_map:
            header_map[normalized] = index
    return header_map


def _decode_csv_text(content: str | bytes) -> str:
    if isinstance(content, str):
        return content.lstrip("\ufeff")
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16").lstrip("\ufeff")
    # Excel "Unicode Text" is UTF-16 without a BOM (NUL bytes between ASCII).
    if b"\x00" in content[:64]:
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                text = content.decode(encoding)
            except UnicodeError:
                continue
            if text.strip("\ufeff"):
                return text.lstrip("\ufeff")
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    return text.lstrip("\ufeff")


def _quote_header(label: str) -> str:
    return f"“{label}”"


def _best_header_cells(text: str) -> list[str]:
    """Header row to describe when the file is missing a required column.

    Prefer the row that already matches the most required names, and prefer a
    row whose label mentions cookies over a title like "Cookie orders".
    """
    best_cells: list[str] = []
    best_score = -1
    for delimiter in _DELIMITERS:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        for index, cells in enumerate(reader):
            if index > _HEADER_SCAN_LIMIT:
                break
            if not any(_clean_cell(cell) for cell in cells):
                continue
            header_map = _header_map_from_cells(cells)
            score = sum(1 for name in REQUIRED_HEADERS if name in header_map)
            if any("cookie" in _clean_cell(cell).lower() for cell in cells):
                score += 1
            if all(name in header_map for name in REQUIRED_HEADERS):
                return cells
            if score > best_score:
                best_score = score
                best_cells = cells
    return best_cells


def _missing_header_error(cells: list[str]) -> RowError:
    header_map = _header_map_from_cells(cells)
    labels = {"name": "Name", "email": "Email", "cookies": "Cookies"}
    missing = [field for field in REQUIRED_HEADERS if field not in header_map]
    missing_labels = [labels[field] for field in missing]
    unrecognized = [
        cleaned
        for cell in cells
        if (cleaned := _clean_cell(cell)) and _normalize_header(cell) is None
    ]
    parts = [
        "Missing required column(s): " + ", ".join(missing_labels) + ".",
        "Use the header Name, Email, Cookies. Comment, Company, Street, Street2, City, State, and Postal Code are optional.",
    ]
    cookie_like = [name for name in unrecognized if "cookie" in name.lower()]
    if "cookies" in missing and cookie_like:
        found = ", ".join(_quote_header(name) for name in cookie_like)
        parts.append(
            f"Found {found} instead of Cookies. Rename it to Cookies. "
            "Put 4 or 12 in the cells, not in the column name."
        )
    elif unrecognized:
        found = ", ".join(_quote_header(name) for name in unrecognized[:6])
        parts.append(f"These headers were not recognized: {found}.")
    return RowError(row=1, message=" ".join(parts))


def _locate_csv_header(text: str) -> tuple[str, int] | None:
    """Find the header record in a Google Sheets / Excel CSV export.

    Spreadsheet locale chooses comma, semicolon, or tab. Users often leave a
    title or ``sep=`` line above the real header. Prefer the earliest row that
    contains Name, Email, and Cookies, and prefer comma when scores tie.
    """
    best: tuple[tuple[int, int, int], str, int] | None = None
    for delimiter in _DELIMITERS:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        for index, cells in enumerate(reader):
            if index > _HEADER_SCAN_LIMIT:
                break
            if not any(_clean_cell(cell) for cell in cells):
                continue
            header_map = _header_map_from_cells(cells)
            if any(h not in header_map for h in REQUIRED_HEADERS):
                continue
            recognized = sum(1 for name in ALL_HEADERS if name in header_map)
            rank = (recognized, -index, 1 if delimiter == "," else 0)
            if best is None or rank > best[0]:
                best = (rank, delimiter, index)
            break
    if best is None:
        return None
    return best[1], best[2]


def _parse_cookie_count(raw: str) -> int | None:
    text = raw.strip()
    if not text:
        return None
    # Allow "cookies-4" / "4 cookies" style values as well as plain integers.
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _validate_email(raw: str) -> str | None:
    try:
        result = validate_email(raw.strip(), check_deliverability=False)
        return result.normalized.lower()
    except EmailNotValidError:
        return None


def parse_gift_orders_csv(
    content: str | bytes,
    *,
    max_rows: int | None = None,
) -> tuple[list[ParsedOrderRow], list[RowError]]:
    """Parse CSV text into order rows.

    Returns (rows, errors). When errors is non-empty, rows may be partial and
    callers should reject the upload without creating orders.
    """
    row_cap = settings.csv_import_max_rows if max_rows is None else max_rows
    text = _decode_csv_text(content)

    if not text.strip():
        return [], [RowError(row=0, message="CSV file is empty.")]

    located = _locate_csv_header(text)
    if located is None:
        cells = _best_header_cells(text)
        if not cells:
            return [], [RowError(row=0, message="CSV file is empty.")]
        return [], [_missing_header_error(cells)]

    delimiter, header_index = located
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header_row: list[str] | None = None
    for index, cells in enumerate(reader):
        if index == header_index:
            header_row = cells
            break
    if header_row is None:
        return [], [RowError(row=0, message="CSV file is empty.")]

    header_map = _header_map_from_cells(header_row)
    if any(h not in header_map for h in REQUIRED_HEADERS):
        return [], [_missing_header_error(header_row)]

    errors: list[RowError] = []
    rows: list[ParsedOrderRow] = []
    data_rows_seen = 0
    for line_index, cells in enumerate(reader, start=header_index + 2):
        # Skip blank lines.
        if not any(_clean_cell(cell) for cell in cells):
            continue

        data_rows_seen += 1
        if row_cap > 0 and data_rows_seen > row_cap:
            errors.append(
                RowError(
                    row=line_index,
                    message=(
                        f"CSV exceeds the maximum of {row_cap} data rows. "
                        "Split the file and import in smaller batches."
                    ),
                )
            )
            return [], errors

        def cell(field: str) -> str:
            idx = header_map.get(field)
            if idx is None or idx >= len(cells):
                return ""
            return _clean_cell(cells[idx])

        name = cell("name")
        email_raw = cell("email")
        cookies_raw = cell("cookies")
        comment_raw = cell("comment")
        company_raw = cell("company")
        street_raw = cell("street")
        street2_raw = cell("street2")
        city_raw = cell("city")
        state_raw = cell("state")
        postal_raw = cell("postal_code")
        address_raw = cell("address")

        row_errors: list[str] = []

        if not name:
            row_errors.append("Name is required.")

        email = _validate_email(email_raw) if email_raw else None
        if email_raw and not email:
            row_errors.append(f"Invalid email: {email_raw!r}.")

        cookie_count = _parse_cookie_count(cookies_raw)
        if cookie_count is None:
            allowed = ", ".join(str(c) for c in sorted(ALLOWED_COOKIE_COUNTS))
            row_errors.append(
                f"Cookies must be one of: {allowed} (got {cookies_raw!r})."
            )
        elif cookie_count not in ALLOWED_COOKIE_COUNTS:
            allowed = ", ".join(str(c) for c in sorted(ALLOWED_COOKIE_COUNTS))
            row_errors.append(
                f"Cookies must be one of: {allowed} (got {cookie_count})."
            )

        note = comment_raw if comment_raw else DEFAULT_IMPORT_NOTE
        if len(note) > NOTE_MAX_LENGTH:
            row_errors.append(
                f"Comment must be at most {NOTE_MAX_LENGTH} characters "
                f"(got {len(note)})."
            )

        address_parts = parts_from_optional(
            company=company_raw,
            street=street_raw,
            street2=street2_raw,
            city=city_raw,
            state=state_raw,
            postal_code=postal_raw,
        )
        address_blob = address_raw.strip() if address_raw else None
        if address_blob == "":
            address_blob = None

        if address_parts and address_parts.has_location_fields() and not address_parts.is_complete():
            row_errors.append(
                "Street, City, State, and Postal Code are required together "
                "(or leave them all blank to email the recipient)."
            )

        resolved = shipping_address_values(parts=address_parts, blob=address_blob)
        address = resolved.get("shipping_address")
        if address_parts and address_parts.is_complete():
            stored_parts = address_parts
        else:
            stored_parts = None

        if address and not email:
            row_errors.append("Email is required when a shipping address is provided.")

        if row_errors:
            for message in row_errors:
                errors.append(RowError(row=line_index, message=message))
            continue

        assert cookie_count is not None and name
        gift_id = COOKIE_COUNT_TO_GIFT_ID[cookie_count]
        request_address = address is None
        rows.append(
            ParsedOrderRow(
                row_number=line_index,
                recipient_name=name,
                recipient_email=email,
                gift_id=gift_id,
                cookie_count=cookie_count,
                note=note,
                shipping_address=address,
                address_parts=stored_parts,
                request_recipient_address=request_address,
            )
        )

    if not rows and not errors:
        errors.append(RowError(row=0, message="CSV has a header but no data rows."))

    return rows, errors
