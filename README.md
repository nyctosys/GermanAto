# GermanATO

Workshop management for GermanATO. The new system lives in `api/` (FastAPI + PostgreSQL) and `web/` (Next.js 16). The old Flask app in `backend/` is kept for reference only.

- How the system works today, module by module (kept current with every change): [docs/SYSTEM_GUIDE.md](docs/SYSTEM_GUIDE.md)
- What the new system must do: [docs/NEW_SYSTEM_SPEC.md](docs/NEW_SYSTEM_SPEC.md)
- How the team tests everything, step by step (tick-off checklist): [docs/TEST_CHECKLIST.md](docs/TEST_CHECKLIST.md)
- What the old app did, page by page (the parity checklist): [docs/feature-inventory/](docs/feature-inventory/README.md)

## Run it locally

Needs PostgreSQL 15+, Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 22 with pnpm.

```bash
createdb germanato
cd api
export DATABASE_URL=postgresql://postgres@127.0.0.1:5432/germanato
uv sync
uv run alembic upgrade head
uv run python -m app.seed --branch-name "GermanATO Lahore" --admin-username owner   # asks for the admin password
uv run uvicorn app.main:app --port 8000 --reload
```

```bash
cd web
pnpm install
pnpm dev            # http://localhost:3000; /api is forwarded to the API on :8000 (API_URL to change it)
```

## Try it with demo data

After the steps above, sign in as the admin you just seeded and walk one car through the workshop (the full picture is in [section 2 of the guide](docs/SYSTEM_GUIDE.md#2-the-life-of-a-car-in-the-workshop)):

1. **Administration → Branch settings:** check the name and tax rate. **Money settings:** the cash, bank and wallet accounts already exist; set the opening balances.
2. **Inventory** and **Labour codes:** add one part with opening stock and one labour code.
3. **Visits → Check in a car:** add the customer and car, then check it in.
4. On the visit: **Job card → Quotation** (price it, send it, record the approval), take an **Advance**, start the **Repair order**, issue the part, mark the work done and move it to **Ready**.
5. **Invoices:** make the invoice, issue it, take the payment with proof, then give the **Gate pass**.
6. Look at what that did: **Dashboard**, **Reports → Finance reports**, **Money in**, **Messages** (queued WhatsApp messages; nothing is sent without Twilio details), and **Reports → Month end** for the checklist.

To run it on a workshop PC with Docker, back it up and connect the cloud, follow [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Tests

```bash
cd api && TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/germanato_test uv run pytest   # a throwaway database: tables are wiped
cd web && pnpm exec next typegen && pnpm exec tsc --noEmit && pnpm lint && pnpm build
```

## How the foundation works

- **Every table** has a time-ordered UUID (v7), `created_by`/`updated_by`, and a `version` for optimistic locking. Branch-owned tables also carry `branch_id`.
- **One flush hook** (`api/app/events.py`) writes the audit log (with the old and new value of each changed field) and the sync outbox for every change, in the same transaction. Routes never log by hand.
- **Sign-in** uses a server-side session behind an httpOnly cookie. Passwords are hashed with scrypt, and an account locks for 15 minutes after 5 wrong passwords.
- **Permissions** are checked on the API with `require("permission")`. The web app only hides what you can't use.
- **Proof files** are identified by their content, not their file name. Each file is stored once per SHA-256, and only within the branch that uploaded it.
