---
name: lab-notes
description: Records a durable lesson in the matching CloseAndKeep agent Log after a mistake, failed approach, or clearly better method. Use when the user asks to record a lesson, save a pitfall, update lab notes, or when a durable failure/success should not be rediscovered next session.
---

# Lab notes

Append one lesson to the matching operating manual. Do not grow files into diaries.

## Where to write

Pick the most specific file:

1. `api/app/integrations/**` → `.cursor/rules/api-integrations.mdc`
2. `api/tests/**` → `.cursor/rules/api-tests.mdc`
3. `api/alembic/**` → `.cursor/rules/api-migrations.mdc`
4. `api/**` → `.cursor/rules/api.mdc`
5. `web/**` → `.cursor/rules/web.mdc`
6. Repo-wide only → `AGENTS.md` Lab notes

Never duplicate the same lesson in root and an area file.

## How to write

- One bullet, one line: what happened, then the rule to follow next time.
- Newest first under **Successes** or **Failures**.
- Cap **8 bullets per list**. If over 8, delete the oldest.
- Do not paste stack traces, secrets, or long docs.

```markdown
- Rejected Checkout amounts above catalog before capture; do not trust Stripe totals alone.
```

## When

- User says to record a lesson, pitfall, or lab note.
- A durable approach failed or a clearly better method was found (not a one-off typo).
