# UI Redesign Plan — Dealer CRM

## Design Direction: "Professional Slate"

**Concept**: A dark top-navigation shell wrapping bright, airy content surfaces. Think automotive-industry internal tools — authoritative, not corporate-bland.

**One thing a user should remember**: Every element belongs to a clear hierarchy. The nav anchors the page. Content breathes. Tables are lists, not spreadsheets.

**Emotional tone**: Precision, trust, speed.

---

## Visual System

### Color Tokens (CSS custom properties in `index.css`)

| Token                   | Value       | Purpose                        |
|-------------------------|-------------|-------------------------------|
| `--nav-bg`              | `#0f172a`   | Top navbar background (slate-900) |
| `--nav-link`            | `#94a3b8`   | Nav link default (slate-400)  |
| `--nav-link-active`     | `#ffffff`   | Active link text              |
| `--nav-active-bg`       | `#1e40af`   | Active link pill (blue-800)   |
| `--color-bg`            | `#f1f5f9`   | App shell background          |
| `--color-surface`       | `#ffffff`   | Card / panel surface          |
| `--color-primary`       | `#2563eb`   | Primary action (blue-600)     |
| `--color-primary-hover` | `#1d4ed8`   | Primary hover (blue-700)      |
| `--color-primary-pale`  | `#eff6ff`   | Primary tint bg               |
| `--color-danger`        | `#ef4444`   | Danger action                 |
| `--color-danger-muted`  | `#fef2f2`   | Danger tint bg                |
| `--color-success`       | `#10b981`   | Success / available           |
| `--color-success-muted` | `#ecfdf5`   | Success tint bg               |
| `--color-warning`       | `#f59e0b`   | Warning / reserved            |
| `--color-warning-muted` | `#fffbeb`   | Warning tint bg               |
| `--color-text`          | `#0f172a`   | Primary text                  |
| `--color-text-2`        | `#334155`   | Secondary body text           |
| `--color-text-3`        | `#64748b`   | Tertiary / muted              |
| `--color-text-4`        | `#94a3b8`   | Placeholder / disabled        |
| `--color-border`        | `#e2e8f0`   | Default border                |
| `--color-border-2`      | `#cbd5e1`   | Stronger border               |
| `--radius-sm`           | `4px`       |                               |
| `--radius-md`           | `8px`       |                               |
| `--radius-lg`           | `12px`      |                               |
| `--shadow-card`         | `0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)` | Subtle card lift |
| `--shadow-modal`        | `0 20px 40px rgba(0,0,0,0.18)` | Modal depth |
| `--font`                | `'Inter', system-ui, -apple-system, sans-serif` | Primary typeface |

### Typography Scale

- Page title (h1/h2): 20px, weight 700, `--color-text`
- Section header: 13px, weight 700, uppercase, letter-spacing 0.07em, `--color-text-3`
- Body: 14px, weight 400, `--color-text-2`
- Small / label: 12px, weight 500, `--color-text-3`
- Micro / badge: 11px, weight 600

### Spacing Rhythm

Pages: `padding: 28px 32px`
Table cells: `padding: 10px 14px`
Card body: `padding: 20px`
Form groups: `gap: 14px`

---

## Component Inventory

### CSS Classes to Define (in `index.css`)

```
/* Navigation */
.nav, .nav-brand, .nav-links, .nav-link, .nav-link.active, .nav-actions

/* Page shell */
.page, .page-header, .page-title, .page-actions

/* Buttons */
.btn                  — base
.btn-primary          — filled blue
.btn-secondary        — outlined
.btn-danger-ghost     — text red, border red on hover
.btn-ghost            — text only
.btn-icon             — icon-sized square

/* Forms */
.form-group, .form-label, .form-hint
.input, .textarea, .select   — consistent sizing + focus ring

/* Tables */
.data-table           — full table container
.data-table th        — uppercase tracking headers
.data-table td        — clean cells
.data-table tbody tr  — row hover state

/* Badges / status pills */
.badge, .badge-success, .badge-warning, .badge-muted, .badge-blue

/* Cards */
.card, .card-header, .card-body

/* Modals */
.modal-overlay, .modal-panel, .modal-header, .modal-body, .modal-footer

/* Search bar */
.search-bar

/* Alert / notice banners */
.notice, .notice-success, .notice-warning, .notice-danger

/* Sidebar */
.sidebar-panel, .sidebar-header

/* FAB */
.fab
```

---

## File-by-File Changes

### 1. `frontend/src/index.css`

**Full rewrite.** Current file: 13 lines of bare resets.

New content:
- `@import` Inter from Google Fonts (via `@import url(...)`)
- All CSS custom property tokens (table above)
- Global resets (current reset preserved + `font-family`, `-webkit-font-smoothing`)
- Custom scrollbar styling (thin, slate-300 thumb)
- All CSS utility classes listed above

No JSX changes needed for this step.

---

### 2. `frontend/src/components/NavBar.tsx`

**Change**: Dark nav bar, refined link states.

Before (conceptual): white bg, gray border-bottom, blue active pills
After:
- `background: var(--nav-bg)` (`#0f172a`)
- Logo: white, 15px, weight 700, with subtle letter-spacing
- Nav links: `className="nav-link"` — slate-400 default, white on hover/active
- Active: `className="nav-link active"` — indigo-800 pill background, white text
- Sign out button: white ghost border (`border: 1px solid rgba(255,255,255,0.2)`, white text)
- Height: 52px (from 48px)

Key inline style to replace: all link styles become className lookups.

---

### 3. `frontend/src/routes/LoginPage.tsx`

**Change**: Centered auth card with atmosphere.

Before: `maxWidth: 360, margin: "100px auto"` — plain
After:
- Full viewport container with `background: var(--color-bg)`
- Centered card: `className="card"` at maxWidth 400px, generous padding
- Logo/brand row above the form with a subtle icon or text treatment
- Better heading: "Welcome back" + subtitle "Sign in to Dealer CRM"
- Inputs: `className="input"` — full focus ring
- Submit button: `className="btn btn-primary"` full-width
- Error: `className="notice notice-danger"`

---

### 4. `frontend/src/App.tsx`

**Change**: Better layout shell, sidebar, FAB.

- App shell background: `var(--color-bg)` (already set via body)
- Sidebar panel: `className="sidebar-panel"` — white surface, better shadow
- Sidebar header: `className="sidebar-header"` — consistent with modal headers
- FAB: `className="fab"` — replaces all inline styles

---

### 5. `frontend/src/routes/CustomersPage.tsx`

**Change**: Page header, table, forms, modals.

**Page layout**:
- `className="page"` outer, `className="page-header"` header row
- Title: `className="page-title"`
- "+ Add Customer" button: `className="btn btn-primary"`
- Search: `className="search-bar"` container, `className="input"` on the `<input>`

**Create form** (inline, not modal):
- Wrap in `className="card"` with padding
- Inputs: `className="input"` or `className="textarea"`
- Labels: `className="form-label"`
- Button: `className="btn btn-primary"`

**Table**:
- `className="data-table"` on `<table>`
- Headers: `className` driven uppercase lettering
- Cars column: badges with `className="badge badge-blue"` for ownership type
- Actions column: Edit `className="btn btn-ghost"`, Delete `className="btn btn-danger-ghost"`

**EditModal**:
- Overlay: `className="modal-overlay"` (includes backdrop blur)
- Panel: `className="modal-panel"` — width 520px, `var(--shadow-modal)`
- Header: `className="modal-header"`
- Body: `className="modal-body"`
- Footer: `className="modal-footer"`
- Inputs → `className="input"`, labels → `className="form-label"`

**NoteModal**:
- Same modal pattern
- Cleaner text rendering: `var(--color-text-2)`, `line-height: 1.7`

---

### 6. `frontend/src/routes/InventoryPage.tsx`

**Change**: Same page/table/modal/form treatment as CustomersPage.

**StatusBadge** component:
- Replace hard-coded `STATUS_STYLES` with CSS classes
  - `available`: `className="badge badge-success"`
  - `reserved`: `className="badge badge-warning"`
  - `sold`: `className="badge badge-muted"`
- Remove inline `STATUS_STYLES` object entirely

**Features/notes in table row**:
- Features: `font-size: 12px`, `var(--color-text-3)`
- Notes (italic amber): keep amber, just use `--color-warning` token

**Duplicate button**: `className="btn btn-ghost"` with blue text color

---

### 7. `frontend/src/routes/OutreachPage.tsx`

**Change**: Cards, toast, form, run modal.

**Page layout**: `className="page"` + `className="page-header"` + `className="page-title"`

**Style guide notice banners**:
- Active: `className="notice notice-success"`
- Missing: `className="notice notice-warning"`

**Create form card**: `className="card"` with `className="card-body"`

**Rule list cards**: `className="card"` per rule, improved hierarchy
- Rule name: 15px, weight 600, `var(--color-text)`
- Rule text: 13px, `var(--color-text-3)`
- Cadence/parsed info: `className="section-header"` treatment (uppercase micro label)
- SQL preview: dark code block `background: #0f172a`, better padding

**Buttons**:
- Run: `className="btn btn-primary"`
- Pause/Activate: `className="btn btn-secondary"`
- Delete: `className="btn btn-danger-ghost"`

**RunModal**:
- Same modal-overlay/modal-panel pattern
- Left panel customer list: compact `className="card"` per customer
- Right panel: cleaner section header, type pills become toggle-button-group style

**Toast**:
- `className="toast"` — styled with `var(--nav-bg)` background, refined radius/shadow

---

### 8. `frontend/src/routes/StylePage.tsx`

**Change**: Page header, categories panel, samples list, profile panel.

**Page layout**: `className="page"` + page header

**Channel tabs**: Convert to `className="tab-group"` with proper active state

**Categories panel**:
- `className="card"` wrapping
- Category pills: `className="badge badge-blue"` with an `×` inside
- Add category row: better input + button alignment

**Add sample form**: `className="card"` + `className="card-body"`

**Sample list items**:
- `className="card"` per sample
- Category select: inline select styled as a badge

**Style profile panel**:
- `className="card"` wrapping MarkdownView
- Summarize button: `className="btn btn-primary"`

---

## Implementation Order

Steps are ordered by dependency (tokens first, layout shell second, pages third):

1. **`index.css`** — full token system + all CSS classes
2. **`NavBar.tsx`** — dark nav (immediately visible)
3. **`LoginPage.tsx`** — first screen users see
4. **`App.tsx`** — layout shell + sidebar + FAB
5. **`CustomersPage.tsx`** — most complex page
6. **`InventoryPage.tsx`** — similar to customers
7. **`OutreachPage.tsx`** — cards + run modal
8. **`StylePage.tsx`** — two-column layout

---

## Constraints

- **No functional changes**: API calls, state, handlers, event logic — untouched
- **No new npm packages**: Inter loaded via Google Fonts CSS import only; no icon library
- **Accessibility preserved**: focus rings via CSS `:focus-visible`, semantic HTML unchanged
- **Responsive**: pages stay readable at narrower desktop widths (1024px+)

---

## Key Files Changed

| File | Change |
|------|--------|
| `frontend/src/index.css` | Full rewrite — tokens + CSS classes |
| `frontend/src/components/NavBar.tsx` | Dark shell nav |
| `frontend/src/routes/LoginPage.tsx` | Auth card with atmosphere |
| `frontend/src/App.tsx` | Layout shell + FAB + sidebar |
| `frontend/src/routes/CustomersPage.tsx` | Tables, forms, modals |
| `frontend/src/routes/InventoryPage.tsx` | Tables, StatusBadge, modals |
| `frontend/src/routes/OutreachPage.tsx` | Cards, run modal, toast |
| `frontend/src/routes/StylePage.tsx` | Categories, samples, profile panel |

---

## SESSION_ID
- CODEX_SESSION: N/A (plan generated by Claude directly from codebase context)
- GEMINI_SESSION: N/A
