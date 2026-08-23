# Responsive System — AIREX

Responsive behavior for the AIREX web app (Next.js + Tailwind). The platform is data-dense; the responsive system preserves **clarity and actionability** at every breakpoint rather than merely shrinking.

---

## 1. Breakpoints

| Token | Width | Layout intent |
|-------|-------|---------------|
| `sm` | ≥ 640 | mobile-large / small tablet |
| `md` | ≥ 768 | tablet (2-col tiles) |
| `lg` | ≥ 1024 | laptop (sidebar + content) |
| `xl` | ≥ 1280 | desktop (full project nav + panels) |
| `2xl` | ≥ 1536 | wide dashboards (max content width 1440) |

Mobile-first: base styles target `< sm`; progressive enhancement upward.

## 2. Navigation Behavior

| Breakpoint | Global nav | Project nav | Breadcrumb |
|------------|-----------|-------------|------------|
| `< md` | **Top bar** (brand, org switcher, bell, user) + **bottom tab bar** (Dashboard, Projects, Research, Settings) | **Drawer** opened from hamburger; items become a scrollable sheet with active highlight | Collapsed to "← Projects / Evaluations"; parent links as chips |
| `md–lg` | Left **icon rail** (48px) with tooltips | Drawer or rail section | Full on demand |
| `≥ lg` | Left **sidebar** (240px) | Persistent **secondary sidebar** (project tabs) | Full breadcrumb |

- Project nav on mobile: the drawer shows the pipeline order (Dashboard, Evaluations, Datasets, Tests, Experiments, Prompts, Models, Traces, Alerts, Reports, Quality Gate, Settings).
- Persistent context: the top bar always shows the **current project name** when inside a project.

## 3. Grid & Layout

| Pattern | Desktop | Mobile |
|---------|---------|--------|
| Metric tiles | 6-col grid (2 rows) | 2-col grid |
| Reliability hero | left 2/3 + right 1/3 (recent evals + alerts) | stacked: score, tiles, lists |
| Detail content | 2-col: main + right rail (meta/actions) | single column; rail becomes collapsible "Details" section |
| Tables | full table with sticky header + sort | **Cards**: each row → card with primary field as title; tap opens detail |
| Compare (models/experiments) | side-by-side table | stacked comparison cards with per-model metric rows |
| Trace waterfall | horizontal with sticky step columns | horizontal scroll (min-width 720px) with hint "swipe →" |
| Diff/version compare | side-by-side panes | toggle between Expected/Actual single pane |
| Forms | 2-col field grid | single column |
| Charts | full width | full width, larger touch tooltips |

## 4. Component Behavior

| Component | Mobile rule |
|-----------|-------------|
| Buttons | min 44×44 px touch target; primary CTA full-width in action bars |
| Tables | transform to card list (see §3); sort/filter via sheet |
| Modals | full-screen sheet (slide-up) with sticky footer actions |
| Drawers | full-screen by default |
| Tabs | horizontally scrollable pill tabs or accordion |
| Toasts | top-center full-width (thumb reach) |
| Stepper | compact: `Queued ✓ Running ● Completed` dots with label of active step |
| Pagination | infinite scroll or "Load more" button |
| Command palette (⌘K) | full-screen search sheet |
| Filters | bottom sheet with Apply/Reset |
| Breadcrumb | collapsed to parent links |

## 5. Dense Data Handling

- **Tables → cards** rule for mobile: define the "title field" per table (e.g., dataset name, evaluation id, rule name) so cards stay scannable.
- **Code/JSON/prompts:** monospace block with horizontal scroll + wrap toggle + copy button.
- **Status chips** remain visible on mobile cards (never color-only; paired with text per DESIGN SYSTEM §2.1).
- **Long lists** (results, traces): virtualization on desktop; "Load more" on mobile.
- **Actions** on cards: explicit primary + "⋯" menu for secondary actions (safe for touch).

## 6. Dashboard on Mobile

- Hero: Reliability Score + delta; expandable "how is this calculated" (weights, transparency §83).
- Metric tiles 2-col; tap a tile → drill to that metric's trend chart.
- Recent evaluations & alerts as cards; pull-to-refresh.
- Live evaluation progress: compact banner pinned at top with progress + Cancel.

## 7. Touch & Input

- No hover-only affordances; all states reachable by tap/focus.
- Numeric inputs use appropriate `inputmode` (numeric/decimal) for thresholds/counts.
- File upload: tap-to-browse + camera-less; drag-drop is progressive enhancement.
- Target size ≥ 44px for all interactive controls (WCAG 2.5.5 guidance).

## 8. Print & Export (support)

- Print stylesheet for reports/detail pages (clean typography, no nav).
- On-screen export remains the primary path (§79); print is a convenience.

## 9. Accessibility in Responsive Mode

- Focus order follows visual order at each breakpoint (no keyboard traps in drawers; Esc closes).
- `aria-expanded` on drawer/tab toggles; focus returns to trigger on close.
- Horizontal-scroll regions announce "scrollable horizontally" + keyboard scroll support.
- Reduced motion respected in drawer/toast transitions.

## 10. PRD Traceability (RESPONSIVE)

| PRD | Element |
|-----|---------|
| §68 pages | all pages render at all breakpoints (verified in PAGE_SPECIFICATIONS mobile fields) |
| §87 dashboard < 3 s | mobile defers charts/secondary panels until after first paint; skeleton-first |
| §86 accessibility | §9 keyboard/ARIA/reduced-motion |
| §79 export | print + on-screen export both available |
