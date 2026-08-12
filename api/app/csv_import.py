"""Parse and validate bulk gift-order CSV uploads."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email

from .config import GIFT_CATALOG, settings
from .shipping_address import ShippingAddressParts, parts_from_optional, shipping_address_values

# Headers accepted (case-insensitive). Address pieces are optional per row.
REQUIRED_HEADERS = ("name", "email", "cookies")
OPTIONAL_HEADERS = (
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

CSV_TEMPLATE_HEADERS = "Name,Email,Cookies,Street,Street2,City,State,Postal Code\n"

# Filled example rows so users can see both known-address and request-address cases.
CSV_EXAMPLE_BODY = (
    "Jane Smith,jane@example.com,4,123 Main St,,Springfield,IL,62704\n"
    "Bob Jones,bob@example.com,4,,,,,\n"
    "Casey NoEmail,,4,,,,,\n"
    "Alex Rivera,alex@example.com,12,456 Oak Ave,Apt 2,Austin,TX,78701\n"
)

DEFAULT_IMPORT_NOTE = "Enjoy these cookies — a small thank-you from us."

_HEADER_ALIASES: dict[str, str] = {
    "name": "name",
    "recipient_name": "name",
    "recipient name": "name",
    "email": "email",
    "recipient_email": "email",
    "recipient email": "email",
    "cookies": "cookies",
    "cookie": "cookies",
    "cookie_count": "cookies",
    "cookie count": "cookies",
    "number of cookies": "cookies",
    "address": "address",
    "shipping_address": "address",
    "shipping address": "address",
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
    "shipping_postal_code": "postal_code",
}


@dataclass(frozen=True)
class ParsedOrderRow:
    row_number: int  # 1-based data row (header is row 1)
    recipient_name: str
    recipient_email: str | None
    gift_id: str
    cookie_count: int
    shipping_address: str | None
    address_parts: ShippingAddressParts | None
    request_recipient_address: bool


@dataclass(frozen=True)
class RowError:
    row: int
    message: str


def template_csv() -> str:
    """Headers-only template for users to fill in."""
    return CSV_TEMPLATE_HEADERS


def example_csv() -> str:
    """Downloadable example with headers and sample rows."""
    return CSV_TEMPLATE_HEADERS + CSV_EXAMPLE_BODY


def _normalize_header(raw: str) -> str | None:
    spaced = re.sub(r"\s+", " ", raw.strip().lower().replace("_", " "))
    underscored = spaced.replace(" ", "_")
    return _HEADER_ALIASES.get(spaced) or _HEADER_ALIASES.get(underscored)


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
    if isinstance(content, bytes):
        # Strip UTF-8 BOM if present (Excel often adds it).
        if content.startswith(b"\xef\xbb\xbf"):
            content = content[3:]
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
    else:
        text = content.lstrip("\ufeff")

    if not text.strip():
        return [], [RowError(row=0, message="CSV file is empty.")]

    reader = csv.reader(io.StringIO(text))
    try:
        header_row = next(reader)
    except StopIteration:
        return [], [RowError(row=0, message="CSV file is empty.")]

    header_map: dict[str, int] = {}
    errors: list[RowError] = []
    for index, cell in enumerate(header_row):
        normalized = _normalize_header(cell)
        if normalized and normalized not in header_map:
            header_map[normalized] = index

    missing = [h for h in REQUIRED_HEADERS if h not in header_map]
    if missing:
        errors.append(
            RowError(
                row=1,
                message=(
                    "Missing required column(s): "
                    + ", ".join(missing)
                    + ". Expected headers: Name, Email, Cookies, Street, Street2, City, State, Postal Code "
                    "(address columns optional)."
                ),
            )
        )
        return [], errors

    rows: list[ParsedOrderRow] = []
    data_rows_seen = 0
    for line_index, cells in enumerate(reader, start=2):
        # Skip blank lines.
        if not any(cell.strip() for cell in cells):
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
            return cells[idx].strip()

        name = cell("name")
        email_raw = cell("email")
        cookies_raw = cell("cookies")
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

        address_parts = parts_from_optional(
            street=street_raw,
            street2=street2_raw,
            city=city_raw,
            state=state_raw,
            postal_code=postal_raw,
        )
        address_blob = address_raw.strip() if address_raw else None
        if address_blob == "":
            address_blob = None

        if address_parts and not address_parts.is_complete():
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
                shipping_address=address,
                address_parts=stored_parts,
                request_recipient_address=request_address,
            )
        )

    if not rows and not errors:
        errors.append(RowError(row=0, message="CSV has a header but no data rows."))

    return rows, errors
