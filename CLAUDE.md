# CLAUDE.md

Rules for every future session working in this repo.

- Read `docs/Plan_v3.md` first; it is the source of truth.
- Money is integer paise. No floats for rupee amounts in storage.
- All times are IST through an injected `Clock`. No `CURRENT_TIMESTAMP` in SQL.
- No constants outside `settings.py`. Secrets only in `.env`, never committed.
- Every metric name comes from `core/features.py`.
- Personas are config objects; one runner serves all personas.
- Work only on branch `v2-ATA`. Small commits. Never push to `main`.
- Do not edit a live database by hand. Use numbered files in `db/migrations/`.
- One task per session; do not build features that were not asked for.
