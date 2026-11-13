"""Gift-note from line: company, else the person's name, within 150 characters."""

from __future__ import annotations

from app.gift_notes import GIFT_NOTE_MAX_LENGTH, from_line_for_sender, note_with_from_line


def test_prefers_company_over_name():
    note = note_with_from_line("Thanks!", company="Acme Corp", name="Ada Seller")
    assert note == "Thanks!\nFrom Acme Corp"


def test_uses_name_when_company_blank():
    note = note_with_from_line("Thanks!", company="  ", name="Ada Seller")
    assert note == "Thanks!\nFrom Ada Seller"


def test_leaves_note_unchanged_without_sender():
    assert note_with_from_line("Thanks!", company=None, name=None) == "Thanks!"
    assert note_with_from_line("Thanks!", company="", name="   ") == "Thanks!"


def test_does_not_duplicate_an_existing_from_line():
    body = "Thanks!\nFrom Acme Corp"
    assert note_with_from_line(body, company="Acme Corp", name="Ada") == body
    assert (
        note_with_from_line("Thanks!\nfrom acme corp", company="Acme Corp", name="Ada")
        == "Thanks!\nfrom acme corp"
    )


def test_collapses_whitespace_in_the_label():
    line = from_line_for_sender(company="Acme\nCorp", name="Ada")
    assert line == "From Acme Corp"


def test_shortens_the_message_so_the_from_line_fits():
    body = "x" * GIFT_NOTE_MAX_LENGTH
    stored = note_with_from_line(body, company="Acme Corp", name="Ada")
    assert len(stored) == GIFT_NOTE_MAX_LENGTH
    assert stored.endswith("\nFrom Acme Corp")
    assert stored.startswith("x")


def test_long_company_is_trimmed_to_the_sticker():
    company = "C" * 400
    line = from_line_for_sender(company=company, name="Ada")
    assert line is not None
    assert len(line) <= GIFT_NOTE_MAX_LENGTH
    assert line.startswith("From ")
    stored = note_with_from_line("Hello", company=company, name="Ada")
    assert len(stored) <= GIFT_NOTE_MAX_LENGTH
    assert stored.endswith(line)


def test_blank_message_is_just_the_from_line():
    assert note_with_from_line("  ", company="Acme Corp", name="Ada") == "From Acme Corp"
