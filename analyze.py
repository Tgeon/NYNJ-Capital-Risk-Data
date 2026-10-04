"""
analyze.py

Loads data/raw_cases.csv, applies the dedup/verification framework, and
computes the exhibits used in the memo and deck:
  - verification & dedup summary (the audit-methodology exhibit)
  - risk index by NY region/county
  - risk index by project type
  - risk index by agency/authority
  - dollar exposure per case
  - timeline view (cases per year)

Outputs data/*.json (small, checked-in) consumed by charts.py and the
report builders.
"""

import json
import pandas as pd

RAW = pd.read_csv("data/raw_cases.csv", parse_dates=["date"])


# ---------------------------------------------------------------------
# 0. Normalize free-text region/agency into a small controlled set for
#    charting and indexing. The raw, more specific strings are kept in the
#    CSV/appendix for citation purposes -- these grouped columns are only
#    used for the exhibits.
# ---------------------------------------------------------------------
def region_group(text):
    t = text.lower()
    # -- New York City / WTC (checked before any "statewide"/NJ text that --
    # -- might also mention a borough in passing) ---------------------------
    if any(k in t for k in ["new york city", "manhattan", "brooklyn", "queens", "bronx",
                             "staten island", "citywide", "roosevelt island",
                             "world trade center", "one world trade", "jfk international"]):
        return "New York City"
    # -- Explicit "statewide"/multi-region signals win over an incidental ---
    # -- city name mentioned parenthetically in the same text --------------
    if "statewide, nj" in t or "statewide (nj" in t or "trenton / statewide" in t:
        return "Statewide / Multi-Region (NJ)"
    if any(k in t for k in ["statewide", "systemwide", "n/a"]):
        return "Statewide / Multi-Region"
    if "ny/nj/ma" in t or ("port authority" in t and "mta" in t):
        return "Statewide / Multi-Region"
    # -- New Jersey buckets --------------------------------------------
    if any(k in t for k in ["newark", "hoboken", "jersey city", "union city", "bergen",
                             "hudson counties", "passaic", "essex county", "roseland"]):
        return "Northern NJ"
    if any(k in t for k in ["trenton", "hamilton township", "edison township", "middlesex",
                             "somerset", "hillsborough", "mercer", "montville", "demarest",
                             "watchung", "morris county", "westfield", "scotch plains",
                             "tinton falls"]):
        return "Central NJ"
    if any(k in t for k in ["camden", "gloucester", "atlantic county", "egg harbor",
                             "delaware river"]):
        return "Southern NJ"
    # -- Remaining NY buckets --------------------------------------------
    if any(k in t for k in ["capital region", "albany", "schenectady", "latham", "colonie"]):
        return "Capital Region"
    if any(k in t for k in ["buffalo", "rochester", "lancaster", "erie county", "holley",
                             "sodus", "monroe county", "western ny", "wny"]):
        return "Western NY"
    if any(k in t for k in ["rockland", "westchester", "valley cottage", "orangeburg",
                             "hudson valley"]):
        return "Hudson Valley"
    if any(k in t for k in ["long island", "suffolk", "east meadow", "westbury", "nassau"]):
        return "Long Island"
    if any(k in t for k in ["syracuse", "new york mills", "central ny", "utica"]):
        return "Central NY"
    if "nyc" in t:
        return "New York City"
    return "Statewide / Multi-Region"


def agency_group(text):
    t = text.lower()
    if "port authority" in t:
        return "Port Authority (NY/NJ)"
    if "schools construction corporation" in t or "(scc)" in t or "schools development authority" in t or "(sda)" in t:
        return "NJ SCC/SDA"
    if "nj dept. of transportation" in t or "njdot" in t:
        return "NJDOT"
    if "delaware river port authority" in t:
        return "DRPA"
    if "njeda" in t or "economic development authority" in t:
        return "NJEDA"
    if "nj municipal redevelopment" in t:
        return "NJ Municipal Redevelopment"
    if "charter school" in t or "township school district" in t or "nj local school districts" in t:
        return "NJ Local School Districts"
    if "nypa" in t or "power authority" in t:
        return "NYPA"
    if "dasny" in t or "dormitory authority" in t:
        return "DASNY"
    if "environmental conservation" in t:
        return "NYS DEC"
    if "office of mental health" in t or "(omh)" in t:
        return "OMH"
    if "nysdot" in t or "nys dept. of transportation" in t:
        return "NYSDOT"
    if "suny polytechnic" in t or "fort schuyler" in t:
        return "SUNY Poly / Fort Schuyler"
    if "executive chamber" in t:
        return "Executive Chamber / ESD"
    if "cuny" in t:
        return "CUNY"
    if "office of general services" in t or t.startswith("ogs"):
        return "OGS"
    if "school construction authority" in t and "nycha" in t:
        return "NYC SCA + NYCHA"
    if "school construction authority" in t:
        return "NYC SCA"
    if "nycha" in t:
        return "NYCHA"
    if "department of education" in t or "(doe)" in t:
        return "NYC DOE"
    if "mta" in t:
        return "MTA"
    if "environmental protection" in t or "water board" in t:
        return "NYC DEP"
    if "dept. of transportation" in t:
        return "NYC DOT"
    return text


RAW["region_group"] = RAW["region"].astype(str).apply(region_group)
RAW["agency_group"] = RAW["agency"].astype(str).apply(agency_group)

# ---------------------------------------------------------------------
# 1. Verification & dedup summary
# ---------------------------------------------------------------------
unique = RAW[~RAW["is_duplicate"]].copy()
n_raw = len(RAW)
n_unique = len(unique)
n_dupe = n_raw - n_unique

verif_counts = unique["verification_class"].value_counts().to_dict()
verif_summary = {
    "n_raw_records": int(n_raw),
    "n_unique_cases": int(n_unique),
    "n_duplicate_records": int(n_dupe),
    "duplicate_rate_pct": round(100 * n_dupe / n_raw, 1),
    "confirmed": int(verif_counts.get("confirmed", 0)),
    "probable": int(verif_counts.get("probable", 0)),
    "uncorroborated": int(verif_counts.get("uncorroborated", 0)),
    "confirmed_pct": round(100 * verif_counts.get("confirmed", 0) / n_unique, 1),
    "probable_pct": round(100 * verif_counts.get("probable", 0) / n_unique, 1),
    "uncorroborated_pct": round(100 * verif_counts.get("uncorroborated", 0) / n_unique, 1),
    "needs_further_verification_pct": round(
        100 * (verif_counts.get("probable", 0) + verif_counts.get("uncorroborated", 0)) / n_unique, 1
    ),
}

# ---------------------------------------------------------------------
# 2. Dollar exposure (avoid double-counting shared-scheme dollars)
# ---------------------------------------------------------------------
dollar_rows = unique[unique["count_in_dollar_total"]].copy()
total_exposure = int(dollar_rows["dollar_amount"].sum())
median_exposure = float(unique.loc[unique["dollar_amount"] > 0, "dollar_amount"].median())

# ---------------------------------------------------------------------
# 3. Risk index by region / project type / agency
# ---------------------------------------------------------------------
def build_index(group_col):
    g = unique.groupby(group_col)
    idx = g.size().rename("case_count").to_frame()
    idx["confirmed_count"] = unique[unique["verification_class"] == "confirmed"].groupby(group_col).size()
    idx["confirmed_count"] = idx["confirmed_count"].fillna(0).astype(int)
    exposure = dollar_rows.groupby(group_col)["dollar_amount"].sum()
    idx["dollar_exposure"] = exposure.reindex(idx.index).fillna(0).astype(int)
    idx = idx.reset_index().sort_values("dollar_exposure", ascending=False)
    return idx

region_idx = build_index("region_group")
type_idx = build_index("project_type")
agency_idx = build_index("agency_group")
state_idx = build_index("state")

# ---------------------------------------------------------------------
# 4. Timeline
# ---------------------------------------------------------------------
unique["year"] = unique["date"].dt.year
timeline = unique.groupby("year").size().rename("case_count").reset_index().sort_values("year")

# ---------------------------------------------------------------------
# 5. Case-stage mix (what kind of enforcement action)
# ---------------------------------------------------------------------
def stage_bucket(s):
    s = s.lower()
    if "dismiss" in s or "vacat" in s:
        return "Dismissed / vacated"
    if "settl" in s or "judgment" in s or "deferred prosecution" in s or "non-prosecution" in s:
        return "Settlement / DPA-NPA"
    if "sentenc" in s or "convict" in s or "guilty" in s:
        return "Criminal conviction / plea / sentence"
    if "charg" in s or "indict" in s:
        return "Charged / indicted"
    if "ig finding" in s or "ig investigation" in s or "referred" in s or "report released" in s:
        return "IG finding / administrative"
    return "Other"

unique["stage_bucket"] = unique["case_stage"].apply(stage_bucket)
stage_mix = unique["stage_bucket"].value_counts().to_dict()

# ---------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------
summary = {
    "verification": verif_summary,
    "dollar_exposure": {
        "total_exposure_counted": total_exposure,
        "median_case_exposure": median_exposure,
        "n_cases_with_disclosed_dollar": int((unique["dollar_amount"] > 0).sum()),
        "n_cases_undisclosed": int((unique["dollar_amount"] == 0).sum()),
    },
    "region_count": int(unique["region_group"].nunique()),
    "agency_count": int(unique["agency_group"].nunique()),
    "date_range": [str(unique["date"].min().date()), str(unique["date"].max().date())],
    "stage_mix": stage_mix,
    "by_state": state_idx.to_dict(orient="records"),
}

with open("data/summary.json", "w") as f:
    json.dump(summary, f, indent=2)

region_idx.to_json("data/index_by_region.json", orient="records", indent=2)
type_idx.to_json("data/index_by_type.json", orient="records", indent=2)
agency_idx.to_json("data/index_by_agency.json", orient="records", indent=2)
state_idx.to_json("data/index_by_state.json", orient="records", indent=2)
timeline.to_json("data/timeline.json", orient="records", indent=2)
unique.to_json("data/cases_unique.json", orient="records", indent=2, date_format="iso")

print(json.dumps(summary, indent=2))
print("\nTop regions by dollar exposure:")
print(region_idx.head(10).to_string(index=False))
print("\nBy project type:")
print(type_idx.to_string(index=False))
print("\nBy agency:")
print(agency_idx.to_string(index=False))
print("\nBy state:")
print(state_idx.to_string(index=False))
