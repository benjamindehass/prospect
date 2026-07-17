# PROSPECT — Project Constitution

Read this before doing anything. If a work session conflicts with this file, this file wins until deliberately amended.

## Mission
Predict where minerals occur from public geologic data (MRDS + Macrostrat), cross-referenced to real parcels later. Built Georgia-first, architected general. Three masters, strict priority order:
1. **Career (primary, hard deadline Oct 1 2026):** self-directed full-stack ML project — Python data/ML back end, TypeScript/React map front end, defensible modeling decisions.
2. **Hobby:** a ranked "go look here" list for Georgia field trips.
3. **Long game (dormant):** land/claims instrument. Do no work for this master before 1 and 2 are fed.

## v0 scope (ship by Oct 1)
- Data: MRDS Georgia extract + Macrostrat point featurization (lith, b_age, t_age, unit, source).
- Model: garnet, binary XGBoost, pseudo-absence sampling (PU setup), spatial-block CV — never random splits.
- Serving: FastAPI endpoint → TypeScript/React MapLibre heatmap of Georgia.
- Validation: one field trip to a high-probability cell; README writeup either way.
- OUT of v0: county GIS layer, alerts/automation, multi-mineral, national deploy, UI polish.

## Architecture rules
- Python = data + ML. TypeScript = user-facing. Boundary is a typed JSON API.
- Georgia is an instance, not an assumption: no state-specific logic in core code, no hardcoded map source IDs (use the smallest-age-span heuristic).
- Every design decision gets an entry in DECISIONS.md: what, why, what was rejected. Mark unimplemented decisions (TODO).
- Cache every Macrostrat response locally; never re-query a point. Sleep between calls. At grid scale, prefer bulk map data over point queries.
- API loops: a bad point costs a row, never the run. Retry (2 attempts, backoff) before declaring a miss; distinguish NO_COVERAGE from FETCH_FAILED.
- Public repo. Reproducible: fixed seeds, requirements.txt current, paths via pathlib relative to repo root.

## Cadence
Mon + Thu evenings, some Saturdays. Ugly end-to-end by Labor Day (data → model → map), then improve. When the time box ends, stop and leave a note for next session. After v0 ships, marginal evenings go to interview prep, not features.

## Milestones
- Jul 13 ✅ day-one join proven
- Jul 16 ✅ get_geology hardened (retries, miss types) and promoted to src/
- Aug 1 — Georgia training table (positives + pseudo-absences, featurized)
- Labor Day — ugly end-to-end heatmap renders in browser
- Sep 15 — honest spatial CV, README solid, deployed publicly
- Oct 1 — v0 shipped, resume bullets written
- Fall — field validation trip + writeup