"""Shared post-connect CRM setup report (Cookie fields + trigger stage)."""

from __future__ import annotations

from typing import Any


def build_setup_report(
    *,
    provider: str,
    object_label: str,
    trigger_stage_name: str,
    missing_fields: list[str],
    unknown_stage: bool,
    extra_messages: list[str] | None = None,
) -> dict[str, Any]:
    """Advisory report: missing fields and unknown stage do not fail OAuth connect."""
    messages: list[str] = []
    for field in missing_fields:
        messages.append(
            f"{field} is missing on {object_label}. "
            "Add this custom field so CloseAndKeep can read it."
        )
    if unknown_stage:
        messages.append(
            f'Trigger stage "{trigger_stage_name}" was not found among {object_label} stages. '
            "Update the name in Integrations or add the stage in your CRM."
        )
    if extra_messages:
        messages.extend(extra_messages)
    ok = not missing_fields and not unknown_stage
    if ok:
        messages.append(
            f'Setup looks good. Cookie fields and trigger stage "{trigger_stage_name}" are present.'
        )
    return {
        "provider": provider,
        "ok": ok,
        "missing_fields": missing_fields,
        "unknown_stage": unknown_stage,
        "trigger_stage_name": trigger_stage_name,
        "messages": messages,
    }
