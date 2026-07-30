# ROADMAP to v0

v0 = honest end-to-end: data → spatially-validated model → rendered GA heatmap.
TypeScript/React/FastAPI serving layer is v0.1, explicitly deferred.

## Done

- Data layer: 509 gold positives + 509 pseudo-absences, featurized (Sessions A/B).
  (Earlier notes said 479 — stale. 509 matches the raw MRDS gold filter exactly:
  300 Past Producer / 178 Prospect / 27 Occurrence / 3 Unknown / 1 Producer.)
- Session C: training_table_v0.csv — 345 pos / 509 neg, 13 features, D7/8/13/14/15.

## Session C — training table [DONE 7/29]

- Merge positives + pseudo_absences; filter to status==OK (no-op: all 1018 were OK)
- Duplicate coords collapsed: 509 records → 345 points (D13)
- Features: age_mid + 10 lith keyword flags (D8); age_span BLOCKED from X (D14)
- Validation layer replacing persona review (D15)
- Output: data/processed/training_table_v0.csv

## Session D — the model [GO SLOW]

- ⟡ DECISION #16: spatial cross-validation. Why random train/test splits
  leak on geodata and inflate metrics; spatial-block CV instead. INTERVIEW CORE.
  (CLAUDE.md calls this "D10" — see DECISIONS entry 7 for the numbering fix.)
- Train XGBoost; honest AUC under spatial CV
- ⟡ DECISION #11: dev_stat as sample_weight (+ sensitivity test: does it move the map?)
- Province-stratified ablation: how much of AUC is geology vs map provenance?
  Open question from Session C — see OPEN below.
- Promote reusable pieces to src/prospect/

## OPEN — needs a call before it can be closed

**The province problem.** Negatives are sampled uniformly across GA (D10a),
but ~half the state is Coastal Plain: young sediment, zero gold. The three age
features alone score 0.86–0.88 univariate AUC, and the only lith flag that
fires is `unconsolidated` (36.7% neg / 0.0% pos). So the model may be learning
"old crystalline north Georgia vs young coastal sand" — true, but it is a
province discriminator, not a prospectivity model. That satisfies no master:
master 2 wants "where in the gold belt do I go", and "north Georgia" is
already known. Candidate fixes: restrict negatives to the crystalline province
(target-group background sampling — contradicts D10a, needs your call), or get
finer lith coverage for the Piedmont (D8 FUTURE). Session D quantifies it
first: report AUC statewide AND within-province. If within-province AUC
collapses toward 0.5, the sampling has to change.

## Session E — grid + heatmap (the visible payoff)

- Generate GA grid; featurize via cache/bulk Macrostrat
- ⟡ DECISION #12: point-API vs bulk data (150k points ≈ 35 days via API — likely bulk)
- Score grid, render folium heatmap
- Commit map image to repo; README shows it

## Session F — ship

- README: how-it-works, honest limitations, the map, findings
- Resume bullet block (FDE + MLE orderings)
- Tag v0
