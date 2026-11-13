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
    missing_stages: list[str] | None = None,
) -> dict[str, Any]:
    """Advisory report: missing fields and unknown stage do not fail OAuth connect."""
    if missing_stages is not None:
        unknown_names = [name for name in missing_stages if name]
        unknown_stage = bool(unknown_names)
    elif unknown_stage:
        unknown_names = [trigger_stage_name]
    else:
        unknown_names = []
    messages: list[str] = []
    for field in missing_fields:
        messages.append(
            f"{field} is missing on {object_label}. "
            "Add this custom field so CloseAndKeep can read it."
        )
    if len(unknown_names) == 1:
        messages.append(
            f'Stage "{unknown_names[0]}" was not found among {object_label} stages. '
            "Update the name in Integrations or add the stage in your CRM."
        )
    elif unknown_names:
        joined = ", ".join(f'"{name}"' for name in unknown_names)
        messages.append(
            f"Recipe stages {joined} were not found among {object_label} stages. "
            "Update the names in Integrations or add the stages in your CRM."
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
