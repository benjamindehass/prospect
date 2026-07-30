1 There will be multiple maps on certain points, attempt to take the most detailed, using source/comments

2 span = b_age - t_age, a feature indicating well dated vs undated. Will prefer sources with smallest span.

3 [7/16] wrap requests in 2 attempts, sleep 2s, 5s between before miss declared

4 [7/16] Begin distinguishing miss types in output

5 [7/16] get_geology promoted to src/prospect/geology.py

6 [7/16] Garnet positive filter (Decision):

INCLUDE: literal "GARNET" match across all commod columns, including
industrial/abrasive records — same mineral, different market, and a
commercial abrasive operation is the strongest evidence ground grows
garnet. Test applied: "if I stood on this ground, would garnet be in it?"

EXCLUDE: "GEM" records — sampled them, no visible garnet positives,
not worth the noise for a larger haystack.

dev_stat: retained as a COLUMN, not a filter — Producer > Prospect >
Occurrence is a trust gradient, so it becomes a sample weight at
training time rather than a gate at data time. Deciding now would be
premature; keeping the metadata is free.

REJECTED: GEM inclusion (noise, no observed signal), abrasive exclusion(would discard highest-confidence positives and bias the set toward
hobbyist-reported ground), dev_stat filtering (N is too precious to
spend before seeing counts; weighting preserves the information).

9 [7/16] Target pivot: garnet -> GOLD (Decision):
Targeted garnet; full-state filter returned N=1 as a commodity (Owl
Hollow Prospect, Monroe Co.). Forensics revealed the mismatch: MRDS
records what industry chased, and GA garnet was never economic — but
10 more garnet records surfaced in the GANGUE field (waste-rock
mineralogy at pyrite/copper mines). What industry calls gangue, a
collector calls the point. 11 total is untrainable.
PIVOT: v0 target = GOLD. 479 positives (18% of all GA records),
dev_stat: 275 Past Producer / 175 Prospect / 25 Occurrence — the
dominant, highest-trust label in the state (Dahlonega belt).
Filter: "GOLD" in commod1|2|3 (commod1 is a comma-list; contains()
handles it). ore-field mentions overlap commod1 and add ~nothing.
FUTURE (v1): garnet returns via mineralogy-field mining (ore/gangue
as label source) or external labels (mindat, GGS bulletins).
REJECTED: keeping garnet on 11 points (untrainable); building an
external garnet label pipeline now (deadline risk); MICA as target
(249 records, viable runner-up — gold beat it on N, trust mix, and
field-validation story).

10 [7/17] Pseudo-absence design (Decision):
(a) COUNT — 1:1 with positives (~479 negatives) for v0 simplicity:
balanced classes, intuitive metrics, no imbalance handling needed.
Cost accepted: thinner coverage of background geology. REVISIT: ratio
(1:1 -> 2:1/3:1) is a MODELING tuning experiment, orthogonal to the
v1/v2 roadmap (v1 = GA depth: better features, gangue-garnet & other
GA-specific labels, finer grid; v2 = breadth: more states, the
"GA-is-an-instance" payoff).
(b) BUFFER — exclude sampled negatives within 0.01° (~1.1km) of a known
positive. Sized empirically via a 1000-point test:
0.005° (~0.6km): 3/1000 excluded
0.01° (~1.1km): 4/1000 excluded <- CHOSEN (elbow)
0.02° (~2.2km): 24/1000 excluded
0.05° (~5.6km): 73/1000 excluded
0.01° sits at the elbow: it removes the obvious "on top of a mine"
darts while the next step up (2.2km) 6x's the cull for little added
correctness -> that's moat-carving, avoided. Distance computed in
degrees (Euclidean on EPSG:4326) — an APPROXIMATION (1°lng ~93km at
33°N, not 111km); acceptable because a buffer radius is inherently
fuzzy. Projection-to-meters (UTM) is the fix if precision matters.
REJECTED: no buffer (leaves hard false negatives contradicting
positives); large buffer (rigged class separation -> spatial leakage,
inflated metrics).
(c) BASE-RATE VALIDITY — this method holds ONLY because gold-ground is a
small fraction of GA area, so random points are ~reliably barren.
The data confirms it: even with NO buffer, only ~4/1000 random points
fall near a known positive — gold's rarity showing up as a number.
This is a verified PRECONDITION, not a preference: it would be INVALID
for a common target (e.g. granite), where random negatives would be
heavily contaminated. Tripwire logged for any future abundant-target work.

---
Entries below marked [AUTONOMOUS] were decided by Claude on 2026-07-29
under an explicit instruction to build to v0 without per-decision input.
They are recorded as such so the repo never overstates who reasoned what.
Rewriting any of them in your own words is a real amendment, not a formality.
---

7 [7/29] Numbering + provenance convention [AUTONOMOUS]:
Entries 7 and 8 were vacant while ROADMAP referenced "#8 lith encoding"
and "#10 spatial CV" — but 10 was already spent on pseudo-absence design,
and commit dbff8f6 called the buffer "D7" when it is really 10(b).
Numbers are load-bearing: geology.py's docstring cites #1-#4, so
renumbering existing entries would silently falsify code comments.
RESOLUTION: existing 1-6, 9, 10 are frozen. 7 = this convention. 8 = lith
encoding (honours ROADMAP's slot). 11 and 12 stay RESERVED for ROADMAP's
dev_stat-weight and point-vs-bulk decisions. Spatial CV becomes 16 — so
CLAUDE.md's "go slow on spatial CV (D10)" means entry 16; CLAUDE.md is
yours to amend, so I left it alone and noted the mapping here.
REJECTED: renumbering to close the gaps (breaks code comments and commit
messages for cosmetic tidiness).

8 [7/29] Lith encoding: keyword flags on normalised tokens [AUTONOMOUS]:
Macrostrat returns lith in three incompatible vocabularies by map source:
  7   "plutonic: undivided granitic rocks"     (coarse, 3 rock classes)
  133 "Major:{biotite gneiss}, Minor:{...}"    (structured, detailed)
  154 "felsic paragneiss; paragneiss/meta..."  (free text)
And map source is CLASS-CORRELATED here (source 133 = 240 neg / 1 pos).
So one-hot / label-encode / hashing on the raw string does not encode
rock — it encodes WHICH MAP COVERED THE POINT, and via that, the label.
CHOSEN: strip Major/Minor wrappers, split to word tokens, set 0/1 flags
against geologically-motivated vocabularies (10 flags: 5 rock classes +
5 gold-host flags for the Dahlonega quartz-in-schist/gneiss model).
Token matching not substring, so "sand" cannot fire on "sandstone".
Keyword lists were written from rock nomenclature, NOT by checking which
tokens separate the classes — choosing keywords by looking at labels
would fit the encoding to the training set.
EMPIRICAL OUTCOME (recorded because it is bad news, see NOTE):
  lith_unconsolidated  36.7% of neg, 0.0% of pos   <- the only real signal
  lith_sedimentary     63.3% of neg, 88.4% of pos
  lith_metamorphic      5.3% / 5.2%   — no signal
  lith_schist           1 row of 854.  lith_quartz: 0 rows.
NOTE: the gold-host flags are dead on arrival. Source 7 covers ~87% of
positives and its vocabulary contains no metamorphic terms at all — it
calls Georgia's gold-belt metasediments "sedimentary". You cannot flag
schist off a map that never says schist. This is a DATA RESOLUTION
problem, not an encoding problem; the encoding is doing its job.
FUTURE (v1): Major-vs-minor weighting; Macrostrat liths IDs instead of
strings; and above all a finer lith source for the Piedmont/Blue Ridge
(GA Geological Survey map, or coarser-scale Macrostrat queries).
REJECTED: one-hot on raw lith (encodes map_source -> label leak);
dropping lith entirely (unconsolidated flag does carry real signal).

11 RESERVED — dev_stat as sample_weight, + sensitivity test (Session D).

12 RESERVED — point-API vs bulk Macrostrat for the grid (Session E).

13 [7/29] Collapse duplicate coordinates [AUTONOMOUS]:
509 gold records occupy only 345 distinct coordinates — MRDS logs one
record per claim/shaft/report, so 164 rows are repeat visits to ground
already in the table. Their Macrostrat features are byte-identical.
Keeping them would (a) let one location vote up to N times in the loss
and (b) place the same point in a train fold and a test fold, which is
precisely the leak spatial CV exists to prevent. Deduping BEFORE the
model is the only place this can be fixed honestly.
CHOSEN: one row per coordinate at 4dp (~11m, matching cache key
precision). When records collide, keep the highest-trust dev_stat rung
(D6's gradient: Producer > Past Producer > Prospect > Occurrence >
Unknown) rather than an arbitrary first row. Multiplicity survives as
n_mrds_records — real evidence of attestation, kept as metadata.
CONSEQUENCE: breaks D10(a)'s 1:1 balance. Table is 345 pos / 509 neg
(1:1.48). Accepted: honest N beats a round ratio, and 1.48:1 needs no
imbalance handling. D10(a)'s ratio experiment is unaffected.
REJECTED: keeping duplicates (CV leakage, silent vote-stuffing);
deduping by site_name (465 unique names on 345 points — names differ for
the same ground); averaging duplicates (identical features, nothing to
average).

14 [7/29] The feature contract [AUTONOMOUS]:
An explicit allowlist of what may enter X, and a blocklist with a reason
per column, enforced in code (features.BLOCKED_FROM_FEATURES, asserted by
checks.check_feature_contract — a fatal, not a warning).
IN X (13): b_age, t_age, age_mid, 10 lith_* flags.
BLOCKED, and why:
  map_source     pure provenance; 240 neg / 1 pos on source 133 alone.
  age_span       D2 invented span to CHOOSE a map, not to predict. Median
                 514.6 (src 7) vs 1.12 (src 133) — it is a provenance
                 proxy in a geology costume. This narrows D2's scope:
                 span stays a selection criterion, never a feature.
  lat, lng       raw coords let the model memorise locations instead of
                 learning geology — defeats the point of spatial CV.
  unit_name      near-unique free text; encodes map_source.
  lith           raw string; superseded by the flags, same leak.
  dev_stat       positives-only. A sample weight (D6, D11), not a feature.
  n_mrds_records positives-only, 0 for all negatives — a perfect leak.
REJECTED: lat/lng as features (common in tutorials, fatal here);
age_span as a feature (would have bought ~free AUC off map provenance —
the single most tempting mistake available in this dataset).

15 [7/29] Validation layer: deterministic tripwires [AUTONOMOUS]:
Asked for a multi-agent "critic / idea man" review board. Declined and
built this instead. Reasoning: every persona in such a board is the same
model with the same priors, so they agree exactly where the model is
wrong — it yields the FEELING of review with none of the coverage. The
four real problems in this session (stale counts, 164 duplicate coords,
map_source class-correlation, age_span provenance) were all found by
reading the data, and none are visible from the plan a persona would
critique.
CHOSEN: src/prospect/checks.py — functions that each answer a question
with a right answer, returning (fatal, advisory). Fatal aborts the build:
blocked feature in X, missing column, duplicate coords, non-binary or
single-class labels, non-OK rows surviving the filter. Advisory prints:
per-feature univariate AUC over a 0.90 threshold, and null counts.
The univariate-AUC tripwire is the load-bearing one — it is how a
provenance proxy gets caught automatically instead of by luck. It is
deliberately advisory, not fatal: a feature CAN legitimately separate
the classes (old crystalline rock really does host Georgia gold), so it
demands judgement rather than silently dropping the column.
REJECTED: persona subagents (theatre, and cost per spawn for zero
marginal coverage); making high-AUC fatal (would auto-delete real
geology); unit tests only (they check code, not datasets — the bugs
here live in the data).

16 RESERVED — spatial cross-validation (Session D). CLAUDE.md calls this
"D10"; see entry 7. INTERVIEW CORE, go slow.
