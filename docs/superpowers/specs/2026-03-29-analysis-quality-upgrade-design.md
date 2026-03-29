# Analysis Quality Upgrade Design

**Scope:** Upgrade per-question analysis output so users can see structured evidence snippets with timestamps and a readable score breakdown in both the report and QA review UI.

## Problem

The current review output has two weaknesses:

1. Evidence is stored as plain strings, so users cannot tell where a quote came from in the interview timeline.
2. Scores are collapsed into a single weighted total without exposing the per-dimension rubric values in the main review surfaces.

This makes the analysis less transparent and harder to trust during replay.

## Recommendation

Add a small structured evidence model to `part_b.schemas`, populate it in `part_b.nodes.topic_analyzer`, and reuse it in both `part_b.reporting` and `ui.analysis_views`.

## Design

### 1. Structured evidence snippets

Add `EvidenceSnippet` to the schema with:
- `text`
- `speaker_role`
- `start_ms`
- `end_ms`
- `turn_id`

Then add `evidence_items` to `TopicAnalysis`.

These snippets will be derived heuristically from candidate turns already present in `TopicGroup.exchanges`. This keeps the feature deterministic and does not require prompt changes.

### 2. Score breakdown helper

Add a helper on `RubricScore` that returns the current score breakdown, including the weighted total.

This avoids duplicating rubric math in the report and UI layers.

### 3. Report and QA review presentation

Update:
- `part_b.reporting` to show a per-question score breakdown table and timestamped evidence list
- `ui.analysis_views` to show the same information in the QA review pane

If timestamped evidence is unavailable, the UI and report should fall back to the existing plain evidence quotes.

## Error Handling

- Evidence extraction should never fail the pipeline. If no timed turns are available, create text-only evidence entries or keep the old quote fallback.
- Existing saved data without `evidence_items` must remain readable because the new field will have a default.

## Testing

- Add regression tests for structured evidence extraction and score breakdown rendering.
- Extend Phase 4 gate expectations so the richer report sections are covered.
