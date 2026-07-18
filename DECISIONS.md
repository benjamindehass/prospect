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
