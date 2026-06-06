# Implementation Plan: Dealer CRM MVP

## Overview
Build the MVP in a dependency-safe order: first establish the shared backend + Postgres foundation, then implement the core CRM workflows, and only after that package the desktop experience.

## Requirements
- FastAPI backend with SQLAlchemy + Alembic
- Postgres-backed data model for customers, inventory, rules, drafts, and style profiles
- JWT-based auth with sales/manager role enforcement
- AI-assisted intake, update, style summarization, rule parsing, and email draft generation
- Desktop packaging path for crm.exe and database.exe
- Cloud-ready configuration and no hardcoded environment assumptions

## Architecture Changes
- Add backend/ for core API, auth, models, services, agents, and LLM abstraction
- Add frontend/ for React/Vite SPA
- Add desktop/ for pywebview + FastAPI launcher
- Add database_app/ for portable Postgres launcher and DB bootstrap
- Add docker-compose.yml for local dev database + backend hot reload

## Implementation Steps

### Phase 1: Foundation
1. Create the monorepo skeleton
   - Action: scaffold backend/, frontend/, desktop/, database_app/, docker-compose.yml
   - Why: the backend must be the shared core for both desktop and cloud migration
   - Dependencies: None
   - Risk: Low

2. Set up local runtime stack
   - Action: add FastAPI, SQLAlchemy, Alembic, Postgres dev container, and config loading
   - Why: all later features depend on a stable runtime
   - Dependencies: Step 1
   - Risk: Medium

### Phase 2: Data + Auth
3. Implement base schema and migrations
   - Action: create users, customers, customer_car, interactions, inventory, sample_messages, style_profiles, outreach_rules, email_drafts
   - Why: this is the real system boundary for all business logic
   - Dependencies: Step 2
   - Risk: Medium

4. Add authentication and permission enforcement
   - Action: implement email/password login, JWT issuance, and sales/manager authorization rules
   - Why: customer isolation must be enforced on the backend, not the UI
   - Dependencies: Step 3
   - Risk: High

### Phase 3: MVP Business Flows
5. Build customer CRUD
   - Action: list/create/update/delete customer records, plus customer_car handling
   - Why: it is the core operational workflow
   - Dependencies: Step 4
   - Risk: Medium

6. Build inventory CRUD
   - Action: manage available cars and sold status
   - Why: inventory is needed for outreach matching and recommendations
   - Dependencies: Step 5
   - Risk: Low

7. Implement AI intake and update flows
   - Action: add Intake Agent and Update Agent with structured outputs and human confirmation
   - Why: this delivers the highest-value AI-assisted workflow
   - Dependencies: Step 5
   - Risk: High

8. Implement style learning
   - Action: store sample messages and generate / refresh style profiles per sales and channel
   - Why: email tone and outreach quality depend on prior examples
   - Dependencies: Step 7
   - Risk: Medium

9. Implement outreach rules and draft generation
   - Action: parse natural-language rules into structured filters, run parameterized SQL, and generate draft emails for approval
   - Why: this is the main differentiator for the product
   - Dependencies: Step 6, Step 8
   - Risk: High

### Phase 4: Desktop Packaging
10. Build desktop launcher and packaging
   - Action: create crm.exe shell with FastAPI + pywebview, plus database.exe launcher for portable Postgres
   - Why: the local dealership deployment path is the first production target
   - Dependencies: Step 9
   - Risk: High

11. Add config and secret handling
   - Action: store non-secret config locally and DB / LLM secrets in OS credential storage
   - Why: this keeps the desktop version practical and supports later cloud migration
   - Dependencies: Step 10
   - Risk: Medium

### Phase 5: Hardening
12. Add validation, tests, and backup support
   - Action: test auth, rule parsing, permission isolation, migrations, and local DB recovery
   - Why: the single DB is the shared truth source and must be reliable
   - Dependencies: Step 10
   - Risk: High

## Testing Strategy
- Unit tests: auth, filter compilation, draft generation helpers
- Integration tests: CRUD endpoints, migration behavior, permission enforcement
- E2E tests: login, customer capture, outreach rule run, draft approval flow

## Risks & Mitigations
- Risk: AI output bypasses security or writes unsafe SQL
  - Mitigation: enforce structured outputs, whitelist fields, and parameterized SQL only
- Risk: desktop DB becomes a single point of failure
  - Mitigation: add backup/restore strategy and clear operational guidance
- Risk: cloud migration becomes harder if config is hardcoded
  - Mitigation: keep all runtime values in config and environment variables

## Success Criteria
- [ ] Backend can start locally with Postgres
- [ ] Sales and manager authentication works
- [ ] Customer and inventory CRUD works with permission boundaries
- [ ] AI intake/update flows produce structured, reviewable outputs
- [ ] Outreach rules generate approved draft emails
- [ ] Desktop packaging path is runnable on Windows
- [ ] All critical tests pass
