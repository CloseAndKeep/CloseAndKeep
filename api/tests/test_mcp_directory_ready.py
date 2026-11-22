"""Claude directory readiness: titles, annotations, description hygiene."""

from __future__ import annotations

import pytest

from app.mcp_tools import TOOL_DEFINITIONS, assert_directory_ready_tools


def test_tool_definitions_are_directory_ready():
    assert_directory_ready_tools(TOOL_DEFINITIONS)


def test_banned_phrase_in_description_fails():
    bad = [
        {
            "name": "bad_tool",
            "title": "Bad",
            "description": "Does a thing. Wait for the seller to say yes.",
            "annotations": {"destructiveHint": True},
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]
    with pytest.raises(AssertionError, match="banned phrase"):
        assert_directory_ready_tools(bad)


def test_missing_title_fails():
    bad = [
        {
            "name": "no_title",
            "description": "Returns data.",
            "annotations": {"readOnlyHint": True},
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]
    with pytest.raises(AssertionError, match="missing title"):
        assert_directory_ready_tools(bad)
