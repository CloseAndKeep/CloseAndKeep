"""Unit tests for CSV gift-order parsing (no HTTP / DB)."""

from __future__ import annotations

from app.csv_import import parse_gift_orders_csv, template_csv, example_csv


def test_template_and_example_helpers():
    assert template_csv().startswith("Name,Email,Cookies,Address")
    example = example_csv()
    assert "jane@example.com" in example
    assert "bob@example.com" in example


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


def test_parse_empty_address_marks_request_flow():
    csv_text = "Name,Email,Cookies,Address\nBob,bob@example.com,4,\n"
    rows, errors = parse_gift_orders_csv(csv_text)
    assert errors == []
    assert rows[0].request_recipient_address is True
    assert rows[0].shipping_address is None
    assert rows[0].gift_id == "cookies-4"


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
