# AGENTS.md

## Project summary
This repository is the planning and implementation foundation for an AI-augmented dealership CRM.

Primary references:
- [ARCHITECTURE.md](ARCHITECTURE.md) — deployment topology, desktop/cloud split, security, and packaging strategy
- [PROJECT.md](PROJECT.md) — MVP scope, roles, data model, and AI workflows
- [PLAN.md](PLAN.md) — implementation roadmap and execution order

## What this repo currently contains
- Architecture and product planning docs are in place.
- The implementation skeleton has not been created yet.
- The next work should follow the phased plan in [PLAN.md](PLAN.md), starting with the shared backend foundation.

## Agent guidance
1. Preserve the existing architecture decisions from [ARCHITECTURE.md](ARCHITECTURE.md).
   - Desktop-first path: shared Postgres + local FastAPI + pywebview shell
   - Cloud migration path: keep backend config-driven and avoid hardcoded deployment assumptions
2. Keep MVP scope aligned with [PROJECT.md](PROJECT.md).
   - Sales/manager roles, customer/inventory/outreach workflows, and AI-assisted drafting are the core goals.
   - Do not expand into real email sending, scheduler jobs, or multi-sales collaboration in the initial MVP.
3. Follow the implementation order in [PLAN.md](PLAN.md).
   - Start with backend/runtime foundation, then schema/auth, then CRM workflows, then desktop packaging.
4. Use configuration over hardcoding.
   - DB host/port, LLM endpoint, secrets, and deployment-specific values should be configurable.
5. Keep security and isolation rules explicit.
   - Enforce backend-side permissions, not UI-only gating.
   - Treat AI output as reviewable, not authoritative.

## Useful conventions to preserve
- Prefer a clean monorepo split: backend/, frontend/, desktop/, database_app/.
- Keep the backend as the shared core that remains portable between desktop and cloud.
- Treat Postgres as the shared truth source in the desktop phase.
- Avoid adding ad-hoc architecture that conflicts with the existing design documents.

## When implementing
- Reuse or extend the existing planning docs instead of inventing a new system design.
- If a new file or module is added, make sure it fits the backend/frontend/desktop/database_app structure described in [ARCHITECTURE.md](ARCHITECTURE.md).
- Update [PLAN.md](PLAN.md) if the execution order changes.
