"""
risk_index.py -- a disclosed, rule-based risk-indicator layer for the
tracker.

This is not a predictive model and doesn't forecast future fraud. It's a
risk-based-audit-planning indicator, like an internal audit function's
annual risk assessment: where has enforcement activity concentrated, how
severe and how recent was it, and so where does independent diligence
belong first. Every number is computed by a fixed, disclosed rule from
fields already in the dataset -- no machine-learning model, no hidden
weighting.

Two outputs:

  1. data/risk_index.json -- one row per (agency, control-category) pair
     that has at least one case, with a risk_tier derived from three
     signals:

       - pervasiveness (from controls.py: Isolated / Recurring / Pervasive)
       - has_material_weakness (whether any case in the pair reached the
         Material Weakness severity tier)
       - recency (share of the pair's cases from the most recent 10 years
         of the dataset's span)

     risk_tier rubric:

       Elevated Focus     -- Pervasive, has a Material Weakness case, and
                              at least half the cases are from the last 10
                              years
       Recurring Pattern  -- Pervasive or Recurring, but doesn't clear the
                              Elevated Focus bar
       Isolated Precedent -- exactly one case

  2. data/state_summaries.json -- one row per state (NY, NJ, NY/NJ) with
     the rollups the state narrative sections are built from: case count,
     dollar exposure, confirmed rate, leading control category and
     archetype, leading agency, and the state's own Elevated Focus pairs.

Caveat, repeated wherever this appears: every case here already cleared
the bar of a public enforcement action or a substantiated audit finding.
This is a lens on where already-substantiated enforcement has
concentrated, not a claim about the underlying rate of fraud at an agency
that's simply never been investigated as closely, and not a prediction
that any specific future project will see fraud.

Reads data/cases_with_controls.json and data/ai_typology.json. Writes
data/risk_index.json and data/state_summaries.json.
"""

import json
from collections import Counter, defaultdict

RECENCY_WINDOW_YEARS = 10  # most recent N years of the dataset's own span

cases = json.load(open("data/cases_with_controls.json"))
typology = {t["case_id"]: t for t in json.load(open("data/ai_typology.json"))}

for c in cases:
    t = typology.get(c["case_id"])
    c["archetype"] = t["archetype"] if t else None

max_year = max(c["year"] for c in cases)
recency_cutoff = max_year - RECENCY_WINDOW_YEARS + 1  # inclusive N-year window


def counted_amount(c):
    return c["dollar_amount"] if c["count_in_dollar_total"] else 0


# ---------------------------------------------------------------------
# 1. risk_index: one row per (agency_group, control_category) pair
# ---------------------------------------------------------------------
pairs = defaultdict(list)
for c in cases:
    pairs[(c["agency_group"], c["control_category"])].append(c)

risk_rows = []
for (agency, category), rows in pairs.items():
    n = len(rows)
    pervasiveness = "Pervasive" if n >= 3 else ("Recurring" if n == 2 else "Isolated")
    has_mw = any(c["severity"] == "Material Weakness" for c in rows)
    n_recent = sum(1 for c in rows if c["year"] >= recency_cutoff)
    recency = n_recent / n

    if pervasiveness == "Pervasive" and has_mw and recency >= 0.5:
        tier = "Elevated Focus"
    elif pervasiveness in ("Pervasive", "Recurring"):
        tier = "Recurring Pattern"
    else:
        tier = "Isolated Precedent"

    exposure = sum(counted_amount(c) for c in rows)
    states = sorted(set(c["state"] for c in rows))

    risk_rows.append({
        "agency_group": agency,
        "control_category": category,
        "case_count": n,
        "states": states,
        "pervasiveness": pervasiveness,
        "has_material_weakness": has_mw,
        "recency_share": round(recency, 2),
        "recent_window": f"{recency_cutoff}-{max_year}",
        "dollar_exposure": exposure,
        "risk_tier": tier,
        "case_ids": [c["case_id"] for c in rows],
    })

TIER_ORDER = {"Elevated Focus": 0, "Recurring Pattern": 1, "Isolated Precedent": 2}
risk_rows.sort(key=lambda r: (TIER_ORDER[r["risk_tier"]], -r["dollar_exposure"]))

with open("data/risk_index.json", "w") as f:
    json.dump(risk_rows, f, indent=2)

tier_counts = Counter(r["risk_tier"] for r in risk_rows)
print("Risk index rows:", len(risk_rows))
for tier in ("Elevated Focus", "Recurring Pattern", "Isolated Precedent"):
    print(f"  {tier:<20} {tier_counts.get(tier, 0)}")

print("\nElevated Focus pairs:")
for r in risk_rows:
    if r["risk_tier"] == "Elevated Focus":
        print(f"  {r['agency_group']} x {r['control_category']}: "
              f"{r['case_count']} cases, ${r['dollar_exposure']:,}, "
              f"{r['recency_share']*100:.0f}% since {r['recent_window'].split('-')[0]}")

# ---------------------------------------------------------------------
# 2. state_summaries: one row per state (NY, NJ, NY/NJ)
# ---------------------------------------------------------------------
state_rows = []
for state in ("NY", "NJ", "NY/NJ"):
    rows = [c for c in cases if c["state"] == state]
    n = len(rows)
    if n == 0:
        continue
    exposure = sum(counted_amount(c) for c in rows)
    n_confirmed = sum(1 for c in rows if c["verification_class"] == "confirmed")

    cat_counts = Counter(c["control_category"] for c in rows)
    cat_exposure = defaultdict(int)
    for c in rows:
        cat_exposure[c["control_category"]] += counted_amount(c)

    arch_counts = Counter(c["archetype"] for c in rows if c["archetype"])

    agency_counts = Counter(c["agency_group"] for c in rows)

    state_elevated = [
        r for r in risk_rows
        if r["risk_tier"] == "Elevated Focus" and state in r["states"]
    ]

    n_recent = sum(1 for c in rows if c["year"] >= recency_cutoff)

    state_rows.append({
        "state": state,
        "case_count": n,
        "confirmed_count": n_confirmed,
        "confirmed_pct": round(100 * n_confirmed / n, 1),
        "dollar_exposure": exposure,
        "recent_case_count": n_recent,
        "recent_window": f"{recency_cutoff}-{max_year}",
        "leading_category_by_count": max(cat_counts, key=cat_counts.get),
        "leading_category_by_count_n": cat_counts[max(cat_counts, key=cat_counts.get)],
        "leading_category_by_exposure": max(cat_exposure, key=cat_exposure.get),
        "leading_category_by_exposure_amt": cat_exposure[max(cat_exposure, key=cat_exposure.get)],
        "leading_archetype": max(arch_counts, key=arch_counts.get) if arch_counts else None,
        "leading_archetype_n": arch_counts[max(arch_counts, key=arch_counts.get)] if arch_counts else 0,
        "leading_agency": max(agency_counts, key=agency_counts.get),
        "leading_agency_n": agency_counts[max(agency_counts, key=agency_counts.get)],
        "elevated_focus_pairs": [
            {"agency_group": r["agency_group"], "control_category": r["control_category"],
             "case_count": r["case_count"], "dollar_exposure": r["dollar_exposure"]}
            for r in state_elevated
        ],
    })

with open("data/state_summaries.json", "w") as f:
    json.dump(state_rows, f, indent=2)

print("\nState summaries:")
for r in state_rows:
    print(f"  {r['state']}: {r['case_count']} cases, ${r['dollar_exposure']:,}, "
          f"leading category = {r['leading_category_by_count']} ({r['leading_category_by_count_n']}), "
          f"leading archetype = {r['leading_archetype']} ({r['leading_archetype_n']}), "
          f"{len(r['elevated_focus_pairs'])} Elevated Focus pair(s)")
