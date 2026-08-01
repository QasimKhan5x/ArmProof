# Focused Context Packs

Context packs are routing documents for one bounded work item. A work item that
references a pack must reference only that pack; the pack chooses exact
sections and files.

Rules:

- keep each pack below 150 lines;
- target fewer than 2,000 loaded lines per task;
- distinguish trusted source/tests/evidence from external or generated input;
- include explicit outputs, verification and stop conditions;
- do not duplicate the full product specification; and
- delete or supersede packs when their work item no longer exists.

Current packs:

- `EVID-001.md`: import established result-first evidence.
- `CAP-001.md`: execute fixed-SLO Graviton capacity validation.
- `TEMPLATE.md`: create future packs consistently.

