"""Feature engineering for the training table.

Implements DECISION #8 (lith keyword flags) and #14 (the feature contract).

Macrostrat lith strings arrive in three mutually incompatible vocabularies
depending on which map covered the point:

    source 7    "plutonic: undivided granitic rocks"
    source 133  "Major:{biotite gneiss}, Minor:{amphibolite,mica schist}"
    source 154  "felsic paragneiss; paragneiss/metavolcanic gneiss"

and in this training set map coverage is class-correlated (source 133 is
240 negatives to 1 positive). So any encoding that keys on the raw string --
one-hot, label-encode, hashing -- learns *which map covered the point*, not
what rock is there. Normalising to a token bag and flagging geologically
motivated vocabulary is what breaks that link: DECISION #8.
"""

import re

# "Major:{...}, Minor:{...}" wrappers carry no rock information at v0.
# Major-vs-minor weighting is a v1 refinement (see DECISION #8, FUTURE).
_WRAPPER = re.compile(r"\b(?:major|minor)\s*:\s*", re.I)
_NON_ALPHA = re.compile(r"[^a-z]+")

# Flags are deliberately NOT mutually exclusive: "metavolcanic" is both
# metamorphic and volcanic, and that is the geologically true answer.
# Vocabulary is chosen from rock nomenclature, never from which tokens
# happen to separate the classes -- picking keywords by looking at the
# labels would fit the encoding to the training set.
LITH_FLAGS: dict[str, set[str]] = {
    "metamorphic": {
        "schist", "schists", "gneiss", "paragneiss", "orthogneiss",
        "phyllite", "slate", "quartzite", "amphibolite", "marble",
        "migmatite", "granulite", "metavolcanic", "metasedimentary",
        "metamorphic", "metaigneous", "greenstone", "serpentinite",
        "soapstone", "metaconglomerate",
    },
    "plutonic": {
        "plutonic", "granite", "granitic", "granodiorite", "diorite",
        "gabbro", "tonalite", "intrusive", "pegmatite", "syenite",
        "ultramafic", "dunite", "peridotite",
    },
    "volcanic": {
        "volcanic", "volcanics", "basalt", "rhyolite", "tuff", "andesite",
        "dacite", "metavolcanic", "greenstone",
    },
    "sedimentary": {
        "sedimentary", "sandstone", "shale", "mudstone", "limestone",
        "dolomite", "dolostone", "conglomerate", "siltstone", "carbonate",
        "chert", "marl", "claystone", "coquina",
    },
    "unconsolidated": {
        "sand", "sands", "clay", "clays", "gravel", "silt", "alluvium",
        "alluvial", "saprolite", "residuum", "regolith", "peat",
    },
    # Gold-host flags. Dahlonega-belt gold sits in quartz veins hosted by
    # metasedimentary and metavolcanic schist/gneiss, commonly near mafic
    # bodies -- so these get their own flags rather than being buried in
    # the coarse rock-class ones.
    "schist": {"schist", "schists", "phyllite"},
    "gneiss": {"gneiss", "paragneiss", "orthogneiss", "migmatite"},
    "quartz": {"quartz", "quartzite", "quartzose"},
    "mafic": {"amphibolite", "gabbro", "basalt", "mafic", "greenstone",
              "ultramafic", "metabasalt"},
    "felsic": {"felsic", "granite", "granitic", "rhyolite", "dacite"},
}

#: Columns that may enter X. DECISION #14.
FEATURE_COLUMNS: list[str] = [
    "b_age",
    "t_age",
    "age_mid",
    *(f"lith_{name}" for name in LITH_FLAGS),
]

#: Columns that must NEVER enter X, each for a stated reason. DECISION #14.
#: checks.check_feature_contract enforces this; it is not advisory.
BLOCKED_FROM_FEATURES: dict[str, str] = {
    "map_source": "which Macrostrat map covered the point; class-correlated "
                  "(source 133 = 240 neg / 1 pos). Pure provenance.",
    "age_span": "b_age - t_age is a dating-confidence metric (DECISION #2's "
                "map-selection criterion), and its median is 514.6 vs 1.12 "
                "by source -- a provenance proxy wearing a geology costume.",
    "unit_name": "free-text unit label, near-unique, encodes map_source.",
    "lith": "raw string; superseded by the lith_* flags for the same reason.",
    "lat": "raw coordinates let the model memorise locations instead of "
           "learning geology, which is what spatial CV exists to prevent.",
    "lng": "see lat.",
    "site_name": "MRDS site label; defined only for positives.",
    "dev_stat": "defined only for positives -- a sample weight (DECISION #6, "
                "#11), never a feature.",
    "n_mrds_records": "defined only for positives (negatives are 0 by "
                      "construction); a perfect label leak if used as X.",
    "status": "pipeline bookkeeping.",
    "label": "the target.",
}


def normalise_lith(raw: object) -> set[str]:
    """Collapse any of the three lith vocabularies to a bag of word tokens.

    Token-level matching (not substring) is deliberate: "sand" must not fire
    on "sandstone", which is a lithified rock, not unconsolidated cover.
    """
    if not isinstance(raw, str):
        return set()
    stripped = _WRAPPER.sub(" ", raw.lower())
    return {tok for tok in _NON_ALPHA.split(stripped) if len(tok) > 2}


def lith_flags(raw: object) -> dict[str, int]:
    """One 0/1 flag per entry in LITH_FLAGS. Unparseable lith -> all zeros."""
    tokens = normalise_lith(raw)
    return {f"lith_{name}": int(bool(tokens & vocab))
            for name, vocab in LITH_FLAGS.items()}


def age_features(b_age: float | None, t_age: float | None) -> dict[str, float]:
    """Age derivations. age_span is computed but blocked from X (#14)."""
    if b_age is None or t_age is None:
        return {"age_mid": float("nan"), "age_span": float("nan")}
    return {"age_mid": (b_age + t_age) / 2.0, "age_span": b_age - t_age}


def add_features(df):
    """Attach every derived feature to a frame carrying lith/b_age/t_age.

    Training rows and grid cells MUST both come through here. If the grid were
    featurized by any other code path, the model would be scoring a different
    feature definition than it was fitted on -- train/serve skew, which is
    invisible in the metrics and fatal to the map. This function existing in
    one place is the guarantee (DECISION #12).
    """
    import pandas as pd

    ages = pd.DataFrame(
        [age_features(b, t) for b, t in
         zip(df["b_age"].where(df["b_age"].notna(), None),
             df["t_age"].where(df["t_age"].notna(), None))],
        index=df.index,
    )
    liths = pd.DataFrame([lith_flags(v) for v in df["lith"]], index=df.index)
    return pd.concat([df, ages, liths], axis=1)
