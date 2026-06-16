# Sales Tips Feature — Implementation Plan

## Overview

A two-phase feature that gives sales reps AI-generated briefings before customer appointments, powered by a flexible knowledge base of support documents.

---

## Phase 1 — Support Doc System

### Goal
Build a CRUD interface where sales can manage a library of support documents. Each document contains a knowledge base (`content`) and an AI execution instruction (`checks`). The system is schema-agnostic — trim alerts, competitor comparisons, incentive notes, and any future category all live in the same table.

### DB Schema

```sql
CREATE TABLE support_docs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category        VARCHAR(50) NOT NULL,   -- e.g. "trim_alert", "competitor", "incentive"
    title           VARCHAR(255) NOT NULL,
    content         TEXT NOT NULL,          -- Raw knowledge text (from sales guides, PDFs, etc.)
    checks          TEXT NOT NULL,          -- AI instruction: what to look for / compare
    effective_from  DATE NOT NULL,
    effective_to    DATE,                   -- NULL = still active
    created_at      TIMESTAMP DEFAULT now()
);
```

**Key design decision:** `checks` is the AI instruction layer. It tells the sub-agent *what to do* with the `content`. The system never needs schema changes to support new alert types — just add a new doc.

### Backend

- `GET    /support-docs` — list all docs (filter by category, effective status)
- `POST   /support-docs` — create new doc
- `PUT    /support-docs/:id` — edit doc
- `DELETE /support-docs/:id` — delete doc
- Helper: `GET /support-docs/active` — returns only docs where `effective_to IS NULL OR effective_to >= today`

### Frontend — Support Info Page

New page in the CRM sidebar: **Support Info**

```
┌─────────────────────────────────────────────┐
│  Support Info                  [+ Add Doc]  │
├──────────────┬──────────────────────────────┤
│ All          │  📋 VW Jetta Trim 2019-2026  │
│ trim_alert   │     trim_alert  •  Active    │
│ competitor   │                              │
│ incentive    │  🏁 Jetta vs Civic 2026      │
│              │     competitor  •  Active    │
│              │                              │
│              │  💰 June 2026 Rate Sheet     │
│              │     incentive  •  Active     │
└──────────────┴──────────────────────────────┘
```

**Add / Edit Doc modal fields:**
- Category (dropdown + free text)
- Title
- Effective From / To
- Content (large textarea — paste from sales guide)
- Checks (textarea — plain English AI instruction)

**Example doc entry:**

```
Category:  trim_alert
Title:     VW Jetta Trim History 2019–2026
Effective: 2019-01-01 → (active)

Content:
  2019: Trendline (base), Comfortline (mid), Highline (mid-high), Execline (top)
  2022: Trendline (base), Comfortline (mid), Highline (top) — Execline discontinued
  2026: Comfortline (base), Highline (top) — Trendline discontinued

Checks:
  Compare the trim the customer purchased against the trim history in Content.
  Identify if the trim's rank (position among all trims that year) has shifted
  relative to its rank today. If the customer's trim is now ranked higher than
  when they bought it, flag this as a trim alert and explain the gap clearly.
```

---

## Phase 2 — Pre-Appointment Briefing Agent

### Goal
When a sales rep opens an appointment, one click triggers an AI orchestrator that runs every active support doc as a sub-agent against the customer's history, then synthesizes a briefing card.

### Architecture

```
Orchestrator
│
├── Input
│   ├── customer deal history (vehicle, trim, year, price, rate, downpay, monthly)
│   └── all active support_docs
│
├── Sub-Agent Fan-out (one per support_doc)
│   │
│   │  system prompt:  doc.checks
│   │  user message:   doc.content + customer history (JSON)
│   │
│   └── returns:
│       {
│         "triggered": true/false,
│         "alert":      "Highline was mid-high in 2019, now it's top trim",
│         "suggestion": "Lead with Comfortline as the apples-to-apples compare"
│       }
│
└── Summarizer Agent
    │
    │  input: all sub-agent results (triggered ones only)
    │
    └── output: final Briefing Card (structured, scannable)
```

### Backend

- `POST /appointments/:id/briefing` — triggers orchestration, returns briefing JSON
- Orchestrator calls Claude API in parallel (one call per active support_doc)
- Summarizer makes one final call to synthesize

### Frontend — Briefing Card (on Appointment detail page)

```
┌─── AI Sales Briefing — John Smith, June 18 ────────────────┐
│                                                             │
│  ⚠️  TRIM ALERT                                             │
│  John bought a 2019 Jetta Highline — that was mid-high     │
│  config at the time (3rd of 4 trims). Today Highline is    │
│  the top trim. He may think the price jumped dramatically.  │
│  → Suggest: compare today's Comfortline as his true apples- │
│    to-apples. Lead with that before he anchors on price.   │
│                                                             │
│  🏁  COMPETITOR WATCH                                        │
│  Honda Civic SI in same price bracket. Current promo:      │
│  0.9% for 60 months. Our advantage: 2-week delivery vs     │
│  6-week wait at Honda right now.                           │
│                                                             │
│  💬  SUGGESTED OPENER                                        │
│  "Your 2019 Highline was a great pick — just so you know,  │
│   the equivalent config today is called Comfortline.        │
│   Let me show you a side-by-side..."                        │
│                                                             │
│  [Regenerate]                            Generated 9:42 AM  │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| One support_docs table, no sub-tables | Adding a new alert type = adding a doc, no code change |
| Sub-agent per doc (parallel) | Isolated, independently testable, easy to add/remove docs |
| `checks` as plain English instruction | Non-technical staff can author new alert types |
| Briefing generated on-demand | Always uses latest support docs + fresh customer data |
| Summarizer as final pass | Deduplicates, prioritizes, and sets tone of the briefing |

---

## Implementation Order

```
Phase 1
  1. DB migration — support_docs table
  2. Backend CRUD routes
  3. Frontend Support Info page (list + add/edit modal)

Phase 2
  4. Orchestrator service (fan-out to sub-agents)
  5. Summarizer agent
  6. POST /appointments/:id/briefing endpoint
  7. Briefing Card UI on appointment detail page
```
