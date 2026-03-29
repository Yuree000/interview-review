# Growth Trend Design

**Scope:** Add a multi-interview trend view so the workspace can show how overall performance and core public dimensions move across saved runs.

## Problem

The project already supports:

1. single-run review artifacts
2. pairwise run comparison
3. aggregated global profile output

What it still lacks is a lightweight longitudinal view between those layers. Users can compare two runs or read a global summary, but they cannot quickly answer:

- is the overall score trending up or down
- which public dimensions are improving most over time
- which repeated weaknesses still show up in recent runs

## Recommendation

Implement a focused `TrendService` in the service layer and expose it at the top of `pages/growth.py`.

## Design

### 1. Build a repository-backed trend payload

Add `services/trend_service.py` with a single responsibility:

- load saved interviews and capability snapshots
- backfill missing snapshots from analyses when possible
- build a stable, sorted timeline payload for UI and export

The payload should include:

- one point per saved run
- overall score and public dimensions for each run
- a compact highlights summary
- repeated weaknesses across the most recent runs

This keeps trend logic out of the page file and avoids pushing more responsibility into `CapabilityService`.

### 2. Keep trend metrics simple and deterministic

The trend summary should be computed from existing snapshot data only:

- `overall_delta`: latest overall minus earliest overall
- `best_improved_dimension`: dimension with the largest positive first-to-last delta
- `biggest_regression_dimension`: dimension with the largest negative first-to-last delta
- `run_count`: number of timeline points

This is intentionally simple. No forecasting, smoothing, or statistical fitting is needed.

### 3. Expose a trend section in Growth

At the top of `pages/growth.py`, render a new trend overview before the two-run compare section:

- metric band for top-line changes
- line chart for overall score over time
- table for dimension deltas from first run to latest run
- repeated-issue block for the most common recent weaknesses
- markdown and JSON export buttons

This turns Growth into both a longitudinal view and a side-by-side comparison workspace.

## Error Handling

- If there are fewer than two usable runs, keep the trend view in a blocked/info state.
- If a run has analyses but no snapshot, build the snapshot on demand.
- If no run has an `overall` dimension, fall back to `0.0` and still render a deterministic payload.

## Testing

- Add service-level regression tests for timeline ordering, delta calculations, repeated-issue aggregation, and export shape.
- Extend Phase 6 gate so the new trend workflow is part of the acceptance baseline.
- Re-run the full pytest suite and all phase gates after implementation.
