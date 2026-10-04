"""
variance_analysis.py -- period-over-period trend analysis and a
driver-based variance breakdown, built on top of controls.py's
control_category field.

Computes two things:
  - a summary of case count, dollar exposure, and confirmed rate for each
    4-year period in the dataset (the same bins charts.py uses for its
    timeline chart)
  - a waterfall: the dollar-exposure change between the two most complete
    adjacent periods, broken down by control category, verified to add up
    exactly to the total change

Reads data/cases_with_controls.json. Writes data/variance_by_period.json
and data/variance_drivers.json.
"""

import json

cases = json.load(open("data/cases_with_controls.json"))


def counted_amount(c):
    return c["dollar_amount"] if c["count_in_dollar_total"] else 0


def period_label(year):
    start = 4 * (year // 4)
    return f"{start}–{start + 3}"


for c in cases:
    c["period"] = period_label(c["year"])

periods = sorted(set(c["period"] for c in cases))

# ---------------------------------------------------------------------
# 1. Period-over-period summary (all 5 periods)
# ---------------------------------------------------------------------
by_period = []
for p in periods:
    rows = [c for c in cases if c["period"] == p]
    n = len(rows)
    confirmed = sum(1 for c in rows if c["verification_class"] == "confirmed")
    exposure = sum(counted_amount(c) for c in rows)
    by_period.append({
        "period": p,
        "case_count": n,
        "dollar_exposure": exposure,
        "confirmed_count": confirmed,
        "confirmed_pct": round(100 * confirmed / n, 1) if n else 0,
    })

with open("data/variance_by_period.json", "w") as f:
    json.dump(by_period, f, indent=2)

print("Period-over-period summary:")
for row in by_period:
    print(f"  {row['period']}: n={row['case_count']:>2}  "
          f"${row['dollar_exposure']:>12,}  confirmed={row['confirmed_pct']}%")

# ---------------------------------------------------------------------
# 2. Waterfall: dollar-exposure variance between the two most COMPLETE
#    periods (the two immediately before the still-in-progress final bin),
#    decomposed by control_category driver.
# ---------------------------------------------------------------------
compare_from, compare_to = periods[-3], periods[-2]  # e.g. "2016-2019" -> "2020-2023"

rows_from = [c for c in cases if c["period"] == compare_from]
rows_to = [c for c in cases if c["period"] == compare_to]

total_from = sum(counted_amount(c) for c in rows_from)
total_to = sum(counted_amount(c) for c in rows_to)

categories = sorted(set(c["control_category"] for c in cases))
drivers = []
for cat in categories:
    exp_from = sum(counted_amount(c) for c in rows_from if c["control_category"] == cat)
    exp_to = sum(counted_amount(c) for c in rows_to if c["control_category"] == cat)
    delta = exp_to - exp_from
    if exp_from == 0 and exp_to == 0:
        continue
    drivers.append({
        "control_category": cat,
        f"exposure_{compare_from}": exp_from,
        f"exposure_{compare_to}": exp_to,
        "delta": delta,
    })

drivers.sort(key=lambda d: -d["delta"])  # largest increase first, largest decrease last

total_delta = total_to - total_from
reconciled = (total_from + sum(d["delta"] for d in drivers)) == total_to

variance_output = {
    "compare_from": compare_from,
    "compare_to": compare_to,
    "total_from": total_from,
    "total_to": total_to,
    "total_delta": total_delta,
    "total_delta_pct": round(100 * total_delta / total_from, 1) if total_from else None,
    "drivers": drivers,
    "reconciled": reconciled,
}

with open("data/variance_drivers.json", "w") as f:
    json.dump(variance_output, f, indent=2)

print(f"\nWaterfall: {compare_from} (${total_from:,}) -> {compare_to} (${total_to:,})")
print(f"Net variance: ${total_delta:,} ({variance_output['total_delta_pct']}%)")
for d in drivers:
    sign = "+" if d["delta"] >= 0 else ""
    print(f"  {d['control_category']:<55} {sign}${d['delta']:,}")
print(f"Reconciles: {reconciled}")
assert reconciled, "Waterfall drivers do not sum to the total variance"
