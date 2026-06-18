# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This is a **planning-only repo** — the implementation skeleton does not exist yet. All code should follow the phased plan in [PLAN.md](PLAN.md), starting with Phase 1 (monorepo scaffold + local runtime stack). The architecture and product decisions are finalized in [ARCHITECTURE.md](ARCHITECTURE.md) and [PROJECT.md](PROJECT.md) — do not reinvent them.

## Planned Monorepo Structure

```
dealer-crm/
├── backend/          # FastAPI core — shared between desktop and cloud
│   └── app/
│       ├── main.py   # FastAPI instance, routes, StaticFiles
│       ├── config.py # All runtime config (DB, LLM, listen address)
│       ├── db.py     # SQLAlchemy engine/session
│       ├── auth/     # JWT, password hashing, role DI
│       ├── models/   # ORM models
│       ├── schemas/  # Pydantic I/O
│       ├── api/      # Routers: auth, customers, inventory, intake, outreach, style
│       ├── services/ # Business logic
│       ├── agents/   # Intake, Update, RuleParser, EmailComposer, StyleSummarizer
│       └── llm/      # LLMClient(base_url, api_key, model)
│   └── alembic/      # Migrations (backend owns schema)
├── frontend/         # React + Vite SPA
│   └── dist/         # Build output, bundled into crm.exe
├── desktop/          # crm.exe packaging
│   ├── shell.py      # Starts uvicorn in thread, opens pywebview
│   └── crm.spec      # PyInstaller spec
├── database_app/     # database.exe packaging
│   ├── launcher.py   # initdb / pg_ctl lifecycle + system tray
│   └── database.spec # PyInstaller onedir spec
└── docker-compose.yml  # Local dev: Postgres + backend hot reload
```

## Development Commands

Once the skeleton exists:

```bash
# Start local dev stack (Postgres + backend hot reload)
docker-compose up

# Backend (from backend/)
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8756

# Run Alembic migrations
alembic upgrade head

# Frontend (from frontend/)
npm install
npm run dev       # dev server
npm run build     # produces dist/ for packaging

# Tests (from backend/)
pytest                        # all tests
pytest tests/test_auth.py     # single file
pytest -k "test_permission"   # single test by name

# Desktop packaging (from desktop/)
pyinstaller crm.spec

# Database launcher packaging (from database_app/)
pyinstaller database.spec
```

## Architecture Decisions to Preserve

**Two-executable deployment**: `database.exe` runs on one always-on LAN machine (portable Postgres); each sales PC runs `crm.exe` (FastAPI + pywebview, binds 127.0.0.1 only).

**FastAPI is the shared core**: the backend must remain identical between the desktop (loopback) and future cloud (central service) deployments. The `desktop/` and `database_app/` directories are desktop-only wrappers that get discarded on cloud migration.

**Configuration over hardcoding**: DB host/port, LLM `base_url`/`api_key`/`model`, and listen address are all config items. Secrets (DB password, LLM key) go into the OS credential store via `keyring`, never plaintext config files.

**Auth is two-layer**:
1. DB layer: all `crm.exe` instances share one `crm_app` Postgres role; `pg_hba.conf` allows only LAN subnet with `scram-sha-256`.
2. App layer: `users` table with argon2/bcrypt hashes; JWT issued on login; FastAPI enforces `assigned_sales_id = current_user.id` for all customer queries (managers bypass this).

**Migrations owned by backend**: `database.exe` only creates the empty `dealer_crm` database and the `crm_app` role. The first `crm.exe` that connects runs `alembic upgrade head` with a Postgres advisory lock to prevent concurrent migration races.

**AI never touches raw SQL**: intake/update use structured tool-calls → ORM insert/update; outreach rule parsing produces a JSON predicate tree → backend compiles to parameterized SQL with a column whitelist. The model cannot generate or execute arbitrary SQL.

**Human approval gates everywhere**: AI output for intake, update, and email drafts always requires sales confirmation before writing to the database or approving for send.

## Data Model Summary

Core tables: `users`, `customers`, `customer_car` (one-to-many), `interactions`, `inventory`, `sample_messages`, `style_profiles`, `outreach_rules`, `email_drafts`.

Key constraints:
- `customers.assigned_sales_id` is the data isolation boundary.
- `inventory` is dealership-wide (not per-sales).
- `style_profiles` stores one row per `(sales_id, channel)` — `email` and `text` channels.
- `email_drafts.status` cycles: `pending → approved | dismissed`.

## The Five AI Agents

| Agent | Trigger | Output |
|-------|---------|--------|
| Intake Agent | Sales describes new customer in chat | Structured field JSON via tool-call → ORM insert after confirmation |
| Update Agent | Sales describes changes in chat | Field diff via tool-call → ORM update after confirmation |
| Style Summarizer | New sample added or manual refresh | Overwrites `style_profiles` row for that sales × channel |
| Rule Parser | Sales saves an outreach rule | JSON predicate tree (whitelist-validated), stored as `compiled_filter` |
| Email Composer | Outreach rule runs | `subject` + `body` draft per matched customer, entered as `email_drafts` |

## MVP Scope Boundaries

**In scope**: login/roles, customer+car CRUD, inventory CRUD, AI intake/update, style learning, outreach rule + draft generation, draft approval inbox.

**Out of scope for MVP**: real email sending, CASL compliance, background schedulers, historical data import, multi-sales collaboration. Outreach is triggered manually by sales, not by a cron job.

## Cloud Migration Discipline

Follow these from the first line of code so migration stays cheap:
1. Backend is stateless (JWT, no local session files).
2. All runtime values in config/env vars — zero hardcoding.
3. Frontend uses relative `/api/...` paths only — never `localhost`.
4. SQLAlchemy data layer is agnostic to portable Postgres vs RDS.
