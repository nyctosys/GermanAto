# GermanATO: notes for any agent working in this repo

Read `progress.txt` (patterns and what is done), `prd.json` (stories; pick the lowest priority number with passes false), and `docs/SYSTEM_GUIDE.md` (how the system works today). The plan is `docs/NEW_SYSTEM_SPEC.md`.

Rules the owner set:
- Stack: Next.js + FastAPI + PostgreSQL; zustand for state, zod for form validation.
- Never read `.env` files or print credentials. Demo and test credentials are for localhost only.
- Do not commit `resolve_duplicate_codes.py`, `merge_reviewed_codes.py` or `.claude/launch.json`.
- Push only to `nyctosys/GermanAto` branch `dev`.
- Document alongside the build: update `docs/SYSTEM_GUIDE.md` in every story's commit.
- Check every new screen at phone, tablet and desktop widths for clipped or overflowing elements.
- Clickable elements must look clickable (DESIGN.md 6b).
- VIN and chassis number are one field. Counter sales print A4 invoices.

One story per commit: implement, run checks (API tests, tsc, lint, Hallmark), verify in the browser, set `passes: true` in prd.json, append learnings to progress.txt, commit, push.
