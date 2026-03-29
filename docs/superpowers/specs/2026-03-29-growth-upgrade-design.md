# Growth Upgrade Design

**Scope:** Upgrade the interview comparison flow so Growth produces clearer summaries, matches shared questions more reliably, and supports direct export from the UI.

## Problem

The current Growth workflow can compare two runs, but it has three practical gaps:

1. Shared-question matching depends on exact `main_question` text, so minor punctuation or wording differences can hide useful topic deltas.
2. The output focuses on raw tables and lacks a concise top-line summary a user can act on immediately.
3. Results stay inside the page; there is no direct export path for markdown or JSON.

## Recommendation

Implement a focused service-layer upgrade in `services.compare_service` and then expose it in `pages/growth.py`.

## Design

### 1. Normalize topic matching

Add a private topic-key normalizer in `CompareService` that:
- lowercases text
- removes spaces and common punctuation
- falls back to `topic_id` if a question string is missing

This keeps the matching logic deterministic and avoids fuzzy search complexity.

### 2. Add comparison highlights

Extend `ComparePayload` with a small `ComparisonHighlights` summary that captures:
- best improved public dimension
- worst regressed public dimension
- weighted-total delta
- shared-topic count

This gives Growth a compact summary band before the detailed tables.

### 3. Add export helpers

Expose a JSON-safe export payload from `CompareService` and add download buttons in `pages/growth.py` for:
- markdown summary
- full comparison JSON

## Error Handling

- If the selected runs cannot be compared because analyses are missing, keep raising `ProjectError`.
- If there are no shared topics, still compute dimension deltas and surface a zero shared-topic count.

## Testing

- Add regression tests for normalized topic matching and comparison highlights.
- Add tests for comparison export payload shape.
- Re-run existing Phase 6 gate to ensure the upgrade stays compatible with current repository fixtures.
