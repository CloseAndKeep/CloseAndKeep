/** Gift-note / bakery sticker field limit — keep in sync with api/app/gift_notes.py */
export const GIFT_NOTE_MAX_LENGTH = 150;

const FROM_PREFIX = "From ";

function oneLine(value: string | null | undefined): string {
  return (value ?? "").split(/\s+/).filter(Boolean).join(" ");
}

/** Company on the account, or the person's name when company is blank. */
export function senderLabel(
  company?: string | null,
  name?: string | null,
): string | null {
  const companyText = oneLine(company);
  if (companyText) return companyText;
  const nameText = oneLine(name);
  return nameText || null;
}

/** `From Acme Corp`, shortened so the line itself fits the bakery sticker. */
export function fromLineForSender(
  company?: string | null,
  name?: string | null,
): string | null {
  let label = senderLabel(company, name);
  if (!label) return null;
  const room = GIFT_NOTE_MAX_LENGTH - FROM_PREFIX.length;
  if (room <= 0) return null;
  if (label.length > room) {
    label = label.slice(0, room).trimEnd();
  }
  if (!label) return null;
  return `${FROM_PREFIX}${label}`;
}

/** Characters left for the personal message once the from line is reserved. */
export function personalNoteLimit(company?: string | null, name?: string | null): number {
  const line = fromLineForSender(company, name);
  if (!line) return GIFT_NOTE_MAX_LENGTH;
  return Math.max(0, GIFT_NOTE_MAX_LENGTH - (line.length + 1));
}

/**
 * Append `From {company or name}` and keep the sticker within 150 characters.
 * Mirrors `note_with_from_line` in api/app/gift_notes.py.
 */
export function noteWithFromLine(
  note: string,
  company?: string | null,
  name?: string | null,
): string {
  const body = note.trim();
  const line = fromLineForSender(company, name);
  if (!line) return body.slice(0, GIFT_NOTE_MAX_LENGTH);
  if (body.toLowerCase().endsWith(line.toLowerCase())) {
    return body.slice(0, GIFT_NOTE_MAX_LENGTH);
  }
  if (!body) return line;
  const suffix = `\n${line}`;
  if (body.length + suffix.length <= GIFT_NOTE_MAX_LENGTH) {
    return `${body}${suffix}`;
  }
  const room = GIFT_NOTE_MAX_LENGTH - suffix.length;
  if (room <= 0) return line;
  const trimmed = body.slice(0, room).trimEnd();
  if (!trimmed) return line;
  return `${trimmed}${suffix}`;
}
