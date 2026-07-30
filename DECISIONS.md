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
