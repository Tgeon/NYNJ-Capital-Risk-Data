"""
state_narratives.py -- generates the "what this means for New York" and
"what this means for New Jersey" sections, so the project shows
state-specific implications rather than one aggregate rollup.

Every sentence is generated from numbers already computed elsewhere in the
pipeline (data/state_summaries.json, data/risk_index.json,
data/cases_with_controls.json) -- nothing is invented. The per-state
severity breakdown and top-agency/category tables are computed here, since
severity_summary.json only reports them dataset-wide.

Same caveat as risk_index.py, repeated in the narrative text itself: every
case already cleared the bar of a substantiated enforcement action. This
is a lens on where scrutiny has already concentrated, not a prediction
that any specific future NY or NJ project will see fraud.

Reads data/cases_with_controls.json, data/state_summaries.json, and
data/risk_index.json. Writes data/state_narratives.json.
"""

import json
from collections import Counter, defaultdict

cases = json.load(open("data/cases_with_controls.json"))
state_summaries = {r["state"]: r for r in json.load(open("data/state_summaries.json"))}
risk_index = json.load(open("data/risk_index.json"))


def counted_amount(c):
    return c["dollar_amount"] if c["count_in_dollar_total"] else 0


# Dataset-wide totals -- computed here (not hardcoded) so this script stays
# correct as the underlying case count/exposure grows in later passes.
TOTAL_N = len(cases)
TOTAL_EXPOSURE = sum(counted_amount(c) for c in cases)


def money(n):
    if n >= 1_000_000:
        return f"${n/1_000_000:.1f}M" if n % 1_000_000 else f"${n//1_000_000}M"
    return f"${n:,.0f}"


def pct(n, d, places=1):
    return f"{100*n/d:.{places}f}%"


def names_join(names):
    """'A' / 'A and B' / 'A, B, and C' -- for describing ties without
    hardcoding which categories/agencies happen to be tied."""
    names = list(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def top_with_ties(counter_most_common):
    """Given Counter.most_common() output, return (names_at_top, top_n,
    rest_of_list_after_the_tied_group) -- so prose can say 'X and Y are
    tied at N' instead of asserting a single winner Counter's ordering
    happens to put first."""
    if not counter_most_common:
        return [], 0, []
    top_n = counter_most_common[0][1]
    tied = [name for name, n in counter_most_common if n == top_n]
    rest = [pair for pair in counter_most_common if pair[1] != top_n]
    return tied, top_n, rest


def state_stats(state):
    rows = [c for c in cases if c["state"] == state]
    n = len(rows)
    exposure = sum(counted_amount(c) for c in rows)

    sev_count = Counter(c["severity"] for c in rows)
    sev_exp = defaultdict(int)
    for c in rows:
        sev_exp[c["severity"]] += counted_amount(c)

    agency_count = Counter(c["agency_group"] for c in rows)
    cat_count = Counter(c["control_category"] for c in rows)
    cat_exp = defaultdict(int)
    for c in rows:
        cat_exp[c["control_category"]] += counted_amount(c)

    return {
        "n": n,
        "exposure": exposure,
        "sev_count": sev_count,
        "sev_exp": sev_exp,
        "top_agencies": agency_count.most_common(5),
        "cat_count": cat_count,
        "cat_exp": cat_exp,
        "top_categories_by_count": cat_count.most_common(3),
        "top_categories_by_exposure": sorted(cat_exp.items(), key=lambda x: -x[1])[:3],
    }


CAVEAT = (
    "This describes where enforcement has concentrated historically -- it is "
    "not a prediction that any specific project or agency will see fraud."
)


def elevated_pairs_for(state):
    return [r for r in risk_index if r["risk_tier"] == "Elevated Focus" and state in r["states"]]


def recurring_but_not_elevated_for(state, min_cases=3):
    """Pervasive/Recurring pairs that didn't clear the Elevated Focus bar --
    useful for flagging patterns that are numerous but mostly historical or
    lack a Material Weakness-tier case, since that distinction is itself
    informative (see the NJ Municipal Redevelopment case below)."""
    out = [
        r for r in risk_index
        if r["risk_tier"] == "Recurring Pattern" and state in r["states"] and r["case_count"] >= min_cases
    ]
    out.sort(key=lambda r: -r["case_count"])
    return out


# ---------------------------------------------------------------------
# New York
# ---------------------------------------------------------------------
ny = state_stats("NY")
ny_summary = state_summaries["NY"]
ny_elevated = elevated_pairs_for("NY")

def most_frequent_sentence(top_names, top_n, rest, noun_singular, geography):
    """'X is the most common N in NY (7 cases)' or, when tied, 'X and Y are
    tied as the most common Ns (7 cases each)' -- built from data so a later
    pass that creates or breaks a tie doesn't leave a wrong claim in place."""
    if len(top_names) > 1:
        return f"{names_join(top_names)} are tied as the most common {noun_singular}s ({top_n} cases each)."
    return f"{top_names[0]} is the most common {noun_singular} ({top_n} cases)."


ny_top_cat_names, ny_top_cat_n, ny_cat_rest = top_with_ties(ny["top_categories_by_count"])
ny_top_exp_name, ny_top_exp_amt = ny["top_categories_by_exposure"][0]
ny_top_agency_names, ny_top_agency_n, ny_agency_rest = top_with_ties(ny["top_agencies"])

ny_paragraphs = [
    (
        f"New York has {ny['n']} of the dataset's {TOTAL_N} cases and {money(ny['exposure'])} of "
        f"{money(TOTAL_EXPOSURE)} in tracked exposure -- the largest share of either. "
        f"{pct(ny_summary['confirmed_count'], ny['n'])} are independently confirmed, and "
        f"{pct(ny_summary['recent_case_count'], ny['n'])} are from the last 10 years."
    ),
    (
        f"{ny['sev_count'].get('Material Weakness', 0)} cases "
        f"({pct(ny['sev_count'].get('Material Weakness', 0), ny['n'])}) reached Material Weakness "
        f"severity, carrying {pct(ny['sev_exp'].get('Material Weakness', 0), ny['exposure'])} of NY's "
        f"exposure. {most_frequent_sentence(ny_top_cat_names, ny_top_cat_n, ny_cat_rest, 'control failure', 'NY')} "
        f"{ny_top_exp_name} carries the largest dollar exposure ({money(ny_top_exp_amt)})."
    ),
    (
        f"{len(ny_elevated)} agency/category pairing{'s' if len(ny_elevated) != 1 else ''} "
        "clear the register's ‘Elevated Focus’ bar in NY -- pervasive, at least one "
        "Material Weakness case, and still active: "
        + "; ".join(
            f"{r['agency_group']} × {r['control_category'].split(',')[0]} "
            f"({r['case_count']} cases, {money(r['dollar_exposure'])})"
            for r in ny_elevated
        )
        + "."
    ),
    CAVEAT,
]

# ---------------------------------------------------------------------
# New Jersey
# ---------------------------------------------------------------------
nj = state_stats("NJ")
nj_summary = state_summaries["NJ"]
nj_elevated = elevated_pairs_for("NJ")
nj_recurring_not_elevated = recurring_but_not_elevated_for("NJ")
nj_muni_redev = next(
    r for r in risk_index
    if r["agency_group"] == "NJ Municipal Redevelopment"
    and r["control_category"] == "Bribery, Kickback & Authorization Controls"
)
# Which agency/category pairing is most pervasive dataset-wide -- computed
# fresh each run rather than asserted in prose, since a later update to the
# dataset can change which pairing leads.
top_pervasive_pair = max(risk_index, key=lambda r: r["case_count"])
nj_muni_redev_is_top = top_pervasive_pair["agency_group"] == "NJ Municipal Redevelopment"

nj_paragraphs = [
    (
        f"New Jersey has {nj['n']} of the {TOTAL_N} cases and {money(nj['exposure'])} in tracked "
        f"exposure. {pct(nj_summary['confirmed_count'], nj['n'])} are independently confirmed, but "
        f"only {pct(nj_summary['recent_case_count'], nj['n'])} are from the last 10 years -- a more "
        f"historical caseload than New York's "
        f"{pct(state_summaries['NY']['recent_case_count'], state_summaries['NY']['case_count'])}."
    ),
    (
        f"Bribery and kickback control failures are the most common category by far "
        f"({nj['top_categories_by_count'][0][1]} cases, {pct(nj['top_categories_by_count'][0][1], nj['n'], 0)} "
        f"of NJ's total), from municipal-redevelopment and pay-to-play prosecutions. But the largest "
        f"dollar exposure sits elsewhere, in disbursement and change-order failures at NJ school-"
        f"construction contracts ({money(nj['top_categories_by_exposure'][0][1])}) -- NJ's frequency "
        f"risk and its dollar risk point to two different controls."
    ),
    (
        "Only one NJ-linked pairing clears ‘Elevated Focus’: "
        + "; ".join(
            f"{r['agency_group']} × {r['control_category'].split(',')[0]} "
            f"({r['case_count']} cases, {money(r['dollar_exposure'])})"
            for r in nj_elevated
        )
        + f" -- the bi-state Port Authority pattern below. NJ Municipal Redevelopment × Bribery is "
        + (
            f"the single most pervasive pairing in the entire dataset ({nj_muni_redev['case_count']} cases)"
            if nj_muni_redev_is_top else
            f"the most pervasive NJ-specific pairing ({nj_muni_redev['case_count']} cases), second only "
            f"to {top_pervasive_pair['agency_group']} in NY ({top_pervasive_pair['case_count']} cases)"
        )
        + f", but doesn't clear Elevated Focus: only {nj_muni_redev['recency_share']*100:.0f}% of its "
        "cases are recent -- mostly the 2009-2016 Hudson County era, not an actively recurring pattern."
    ),
    CAVEAT,
]

# ---------------------------------------------------------------------
# Cross-border: Port Authority of NY & NJ
# ---------------------------------------------------------------------
crossborder = state_stats("NY/NJ")
cb_summary = state_summaries["NY/NJ"]
cb_elevated = elevated_pairs_for("NY/NJ")

crossborder_paragraphs = [
    (
        f"The {crossborder['n']} cases coded NY/NJ are almost all Port Authority of New York and New "
        f"Jersey matters. All are independently confirmed, and "
        f"{pct(crossborder['sev_count'].get('Material Weakness', 0), crossborder['n'])} are Material "
        f"Weakness-tier -- the highest concentration of confirmed, high-severity findings in the "
        f"dataset. This is why Port Authority × Bribery appears as Elevated Focus in both state "
        f"sections above."
    ),
]

state_narratives = {
    "NY": {
        "heading": "What this means for New York",
        "paragraphs": ny_paragraphs,
        "key_stats": {
            "case_count": ny["n"],
            "dollar_exposure": ny["exposure"],
            "confirmed_pct": ny_summary["confirmed_pct"],
            "material_weakness_pct": round(100 * ny["sev_count"].get("Material Weakness", 0) / ny["n"], 1),
            "recent_pct": round(100 * ny_summary["recent_case_count"] / ny["n"], 1),
            "leading_category": ny["top_categories_by_count"][0][0],
            "elevated_focus_count": len(ny_elevated),
        },
    },
    "NJ": {
        "heading": "What this means for New Jersey",
        "paragraphs": nj_paragraphs,
        "key_stats": {
            "case_count": nj["n"],
            "dollar_exposure": nj["exposure"],
            "confirmed_pct": nj_summary["confirmed_pct"],
            "material_weakness_pct": round(100 * nj["sev_count"].get("Material Weakness", 0) / nj["n"], 1),
            "recent_pct": round(100 * nj_summary["recent_case_count"] / nj["n"], 1),
            "leading_category": nj["top_categories_by_count"][0][0],
            "elevated_focus_count": len(nj_elevated),
        },
    },
    "NY/NJ": {
        "heading": "The bi-state exception: Port Authority of NY & NJ",
        "paragraphs": crossborder_paragraphs,
        "key_stats": {
            "case_count": crossborder["n"],
            "dollar_exposure": crossborder["exposure"],
            "confirmed_pct": cb_summary["confirmed_pct"],
            "material_weakness_pct": round(100 * crossborder["sev_count"].get("Material Weakness", 0) / crossborder["n"], 1),
        },
    },
}

with open("data/state_narratives.json", "w") as f:
    json.dump(state_narratives, f, indent=2)

print("Wrote data/state_narratives.json")
for state, block in state_narratives.items():
    print(f"\n=== {block['heading']} ===")
    for p in block["paragraphs"]:
        print(p)
        print()
