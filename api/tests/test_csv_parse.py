"""Unit tests for CSV gift-order parsing (no HTTP / DB)."""

from __future__ import annotations

from app.csv_import import parse_gift_orders_csv, template_csv, example_csv


def test_template_and_example_helpers():
    assert template_csv().startswith(
        "Name,Email,Cookies,Company,Street,Street2,City,State,Postal Code"
    )
    example = example_csv()
    assert "jane@example.com" in example
    assert "bob@example.com" in example
    assert "Springfield" in example


def test_parse_accepts_header_aliases():
    csv_text = (
        "Recipient Name,Recipient Email,Cookie Count,Shipping Address\n"
        "Jane,jane@example.com,4,123 Main\n"
    )
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert len(rows) == 1
    assert rows[0].recipient_name == "Jane"
    assert rows[0].gift_id == "cookies-4"
    assert rows[0].shipping_address == "123 Main"
    assert rows[0].request_recipient_address is False


def test_parse_structured_address_columns():
    csv_text = (
        "Name,Email,Cookies,Company,Street,Street2,City,State,Postal Code\n"
        "Jane,jane@example.com,4,Acme Corp,123 Main St,Apt 2,Springfield,IL,62704\n"
    )
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert rows[0].shipping_address == "Acme Corp\n123 Main St\nApt 2\nSpringfield, IL 62704"
    assert rows[0].address_parts is not None
    assert rows[0].address_parts.company == "Acme Corp"
    assert rows[0].address_parts.city == "Springfield"
    assert rows[0].request_recipient_address is False


def test_parse_incomplete_structured_address_is_error():
    csv_text = (
        "Name,Email,Cookies,Street,City,State,Postal Code\n"
        "Jane,jane@example.com,4,123 Main St,,,62704\n"
    )
    rows, errors = parse_gift_orders_csv(csv_text)
    assert rows == []
    assert any("street, city, state, and postal code" in e.message.lower() for e in errors)


def test_parse_empty_address_marks_request_flow():
    csv_text = "Name,Email,Cookies,Address\nBob,bob@example.com,4,\n"
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert rows[0].request_recipient_address is True
    assert rows[0].shipping_address is None
    assert rows[0].gift_id == "cookies-4"


def test_parse_blank_email_allowed_for_request_flow():
    csv_text = "Name,Email,Cookies,Address\nCasey,,4,\n"
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert rows[0].recipient_email is None
    assert rows[0].request_recipient_address is True


def test_parse_blank_email_rejected_when_address_present():
    csv_text = "Name,Email,Cookies,Address\nCasey,,4,123 Main\n"
    rows, errors = parse_gift_orders_csv(csv_text)
    assert rows == []
    assert any("email is required" in e.message.lower() for e in errors)


def test_parse_strips_utf8_bom():
    content = b"\xef\xbb\xbfName,Email,Cookies,Address\nJane,jane@example.com,4,1 Main\n"
    rows, errors = parse_gift_orders_csv(content)
    assert errors == []
    assert len(rows) == 1


def test_parse_skips_blank_lines():
    csv_text = "Name,Email,Cookies,Address\n\nJane,jane@example.com,4,1 Main\n\n"
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert len(rows) == 1


def test_parse_empty_file():
    rows, errors = parse_gift_orders_csv("")
    assert rows == []
    assert errors and "empty" in errors[0].message.lower()


def test_parse_header_only_is_error():
    rows, errors = parse_gift_orders_csv("Name,Email,Cookies,Address\n")
    assert rows == []
    assert any("no data" in e.message.lower() for e in errors)


def test_parse_cookie_count_from_text():
    csv_text = "Name,Email,Cookies,Address\nJane,jane@example.com,4 cookies,1 Main\n"
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert rows[0].cookie_count == 4


def test_parse_google_sheets_semicolon_two_rows():
    csv_text = (
        "Name;Email;Cookies;Company;Street;Street2;City;State;Postal Code\n"
        "Jane Smith;jane@example.com;4;;123 Main St;;Springfield;IL;62704\n"
        "Bob Jones;bob@example.com;12;Acme;456 Oak Ave;;Austin;TX;78701\n"
    )
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert len(rows) == 2
    assert rows[0].shipping_address is not None
    assert "Springfield" in rows[0].shipping_address
    assert rows[1].address_parts is not None
    assert rows[1].address_parts.city == "Austin"
    assert rows[1].cookie_count == 12


def test_parse_google_sheets_tab_and_title_row():
    csv_text = (
        "Cookie orders\n"
        "Name\tEmail\tCookies\n"
        "Jane Smith\tjane@example.com\t4\n"
        "Bob Jones\tbob@example.com\t12\n"
    )
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert [row.recipient_name for row in rows] == ["Jane Smith", "Bob Jones"]
    assert rows[0].request_recipient_address is True


def test_parse_google_sheets_bom_crlf_quoted_two_rows():
    text = (
        '"Name","Email","Cookies","Company","Street","Street2","City","State","Postal Code"\r\n'
        '"Jane Smith","jane@example.com","4","","123 Main St","","Springfield","IL","62704"\r\n'
        '"Bob Jones","bob@example.com","12","Acme, Inc","456 Oak Ave","","Austin","TX","78701"\r\n'
    )
    raw = b"\xef\xbb\xbf" + text.encode("utf-8")
    rows, errors = parse_gift_orders_csv(raw)
    assert errors == []
    assert len(rows) == 2
    assert rows[1].address_parts is not None
    assert rows[1].address_parts.company == "Acme, Inc"


def test_parse_utf16_and_leading_blank_line():
    text = "\nName,Email,Cookies\nJane,jane@example.com,4\nBob,bob@example.com,12\n"
    rows, errors = parse_gift_orders_csv(text.encode("utf-16"))
    assert errors == []
    assert len(rows) == 2
    assert rows[1].gift_id == "cookies-12"


def test_parse_ignores_zero_width_space_in_postal_header():
    csv_text = (
        "Name,Email,Cookies,Company,Street,Street2,City,State,Postal\u200b Code\n"
        "Jane Smith,jane@example.com,4,,123 Main St,,Springfield,IL,62704\n"
        "Bob Jones,bob@example.com,12,,,,,,\n"
    )
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert len(rows) == 2
    assert rows[0].address_parts is not None
    assert rows[0].address_parts.postal_code == "62704"
    assert rows[1].request_recipient_address is True


def test_parse_collects_multiple_row_errors():
    csv_text = (
        "Name,Email,Cookies,Address\n"
        ",bad-email,99,\n"
        "Ok,ok@example.com,4,1 Main\n"
    )
    rows, errors = parse_gift_orders_csv(csv_text)
    assert len(rows) == 1
    assert len(errors) >= 2
    messages = " ".join(e.message for e in errors)
    assert "Name is required" in messages
    assert "Invalid email" in messages or "Cookies must be" in messages
