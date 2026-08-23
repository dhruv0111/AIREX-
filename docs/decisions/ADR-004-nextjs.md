# ADR-004: Next.js for the Frontend

**Status:** Accepted

## Context
The PRD specifies Next.js + React + TypeScript + Tailwind (PRD §67) and requires a fast initial dashboard load (< 3 s, §87) and accessibility (§86).

## Decision
Use **Next.js 15 (App Router)** with React Server Components for page shells and client components for interactive surfaces (forms, dashboards). TanStack Query for server-state; Tailwind CSS for styling; Recharts for charts.

## Alternatives
- Vite SPA — faster dev but weaker SSR/SEO and initial-load story.
- Remix/SvelteKit — different ecosystem, PRD names Next.js.

## Consequences
- Pros: SSR for fast dashboards, typed client, large ecosystem.
- Cons: build complexity; mitigated by a lean Phase 0 surface.
