"""
controls.py -- internal-controls layer on top of the case dataset.

Adds three fields to every case, each assigned by reading the case
individually rather than matching keywords:

  1. control_category -- the single primary internal-control failure the
     case illustrates (procurement/bid integrity, MWBE-DBE and professional
     certification, payroll, disbursement/invoice, bribery/authorization,
     conflict of interest, or economic-development/tax-incentive). Many
     cases touch more than one control area; this field names the
     root-cause control that let the scheme happen, not every control it
     touched.

  2. magnitude_tier -- High (>=$1,000,000), Medium ($100,000-$999,999),
     Low (<$100,000), or Undisclosed, based on the case's own dollar
     amount. This reflects what's known about the case itself, separate
     from whether that dollar figure is counted toward the aggregate
     total (to avoid double-counting a shared scheme).

  3. severity -- Material Weakness, Significant Deficiency, or Control
     Deficiency (the standard three-tier internal-controls classification),
     applied with a fixed, two-factor rule:

       pervasiveness = how many OTHER cases in the dataset share the same
       agency and control category -- Isolated (1), Recurring (2),
       Pervasive (3+).

       severity = Material Weakness      if magnitude is High, or Medium
                                          and Pervasive
                = Significant Deficiency if magnitude is Medium (and not
                                          above), or Low/Undisclosed and
                                          Recurring or Pervasive
                = Control Deficiency     otherwise

     Caveat: every case here already cleared the bar of a public
     enforcement action, so this severity mix isn't a representative
     sample of a control environment -- it's a sample of already-
     substantiated failures, which skews toward higher severity. Treat it
     as a way to organize findings, not a claim about the overall health
     of these agencies' controls.

One category, "Economic-Development & Tax-Incentive Controls", covers two
New Jersey cases (the Holtec/Singh tax-credit settlement and the dismissed
Norcross indictment) that are a different kind of control problem --
subsidy/incentive compliance rather than procurement, payroll, or
disbursement controls on a construction project.

Reads data/cases_unique.json (written by analyze.py). Writes
data/cases_with_controls.json, data/controls_by_category.json, and
data/severity_summary.json.
"""

import json
from collections import Counter, defaultdict

cases = json.load(open("data/cases_unique.json"))

# ---------------------------------------------------------------------
# 1. Control category -- hand-assigned per case (see module docstring).
#    One line of rationale per case, in violation_type order as they appear in
#    data/raw_cases.csv, so a reviewer can check each call against the summary.
# ---------------------------------------------------------------------
CONTROL_CATEGORY = {
    # -- Procurement & Bid-Integrity Controls -------------------------------
    "ny-suny-2026-final": "Procurement & Bid-Integrity Controls",       # RFPs secretly tailored to predetermined winners
    "ny-mta-2022-berlangero-s": "Procurement & Bid-Integrity Controls", # confidential pricing leaked to steer the award
    "ny-dep-2018-dandb": "Procurement & Bid-Integrity Controls",        # procurement info leaked for steered subcontracts
    "ny-dep-2020-chlupsa-dismissed": "Procurement & Bid-Integrity Controls",  # same scheme as dandb, charges later dismissed

    # -- MWBE/DBE & Professional-Certification Controls ---------------------
    "ny-cap-2018-s": "MWBE/DBE & Professional-Certification Controls",       # identity theft used to fabricate MWBE credit
    "ny-dasny-2019-nichter": "MWBE/DBE & Professional-Certification Controls",
    "ny-dasny-2019-coler": "MWBE/DBE & Professional-Certification Controls",
    "ny-dasny-2024-scottlawn": "MWBE/DBE & Professional-Certification Controls",
    "ny-dasny-2024-javen": "MWBE/DBE & Professional-Certification Controls",
    "ny-mta-2013-kleinberg": "MWBE/DBE & Professional-Certification Controls",
    "ny-mta-2019-ahern": "MWBE/DBE & Professional-Certification Controls",
    "ny-mta-2021-tower": "MWBE/DBE & Professional-Certification Controls",
    "ny-mta-2021-spectrum": "MWBE/DBE & Professional-Certification Controls",
    "ny-mta-2015-granite": "MWBE/DBE & Professional-Certification Controls",
    "ny-dep-2014-schlesinger": "MWBE/DBE & Professional-Certification Controls",  # false Master Electrician supervision certification

    # -- Payroll, Timekeeping & Certified-Payroll Controls -------------------
    "ny-nypa-2015-delaney": "Payroll, Timekeeping & Certified-Payroll Controls",  # ghost employees on certified payroll/invoices
    "ny-nypa-2016-sheridan": "Payroll, Timekeeping & Certified-Payroll Controls",
    "ny-mta-2020-overtime": "Payroll, Timekeeping & Certified-Payroll Controls",  # fabricated overtime hours
    "ny-mta-2026-rocco": "Payroll, Timekeeping & Certified-Payroll Controls",
    "ny-sca-2016-nadeem-sentenced": "Payroll, Timekeeping & Certified-Payroll Controls",
    "ny-sca-2020-kumar": "Payroll, Timekeeping & Certified-Payroll Controls",
    "ny-doe-2025-temco": "Payroll, Timekeeping & Certified-Payroll Controls",
    "ny-scanycha-2016-final": "Payroll, Timekeeping & Certified-Payroll Controls",

    # -- Disbursement, Invoice & Change-Order Controls ------------------------
    "ny-ogs-2011-01": "Disbursement, Invoice & Change-Order Controls",   # altered invoices, no official bribed
    "ny-dasny-2024-seabreeze": "Disbursement, Invoice & Change-Order Controls",
    "ny-dot-2019-s": "Disbursement, Invoice & Change-Order Controls",     # billed for chemicals never purchased
    "ny-cuny-2026-01": "Disbursement, Invoice & Change-Order Controls",   # falsified change orders

    # -- Bribery, Kickback & Authorization Controls ---------------------------
    "ny-ogs-2014-01": "Bribery, Kickback & Authorization Controls",  # official bribed to approve fraudulent reimbursements
    "ny-omh-2009-01": "Bribery, Kickback & Authorization Controls",
    "ny-dec-2016-01": "Bribery, Kickback & Authorization Controls",  # official abused approval authority for personal gain
    "ny-percoco-2018-01": "Bribery, Kickback & Authorization Controls",
    "ny-mta-2018-lokhandwala": "Bribery, Kickback & Authorization Controls",
    "ny-nycha-2024-harris": "Bribery, Kickback & Authorization Controls",
    "ny-nycha-2025-final": "Bribery, Kickback & Authorization Controls",
    "ny-dep-2022-djurasevic": "Bribery, Kickback & Authorization Controls",
    "ny-nycdot-2008-01": "Bribery, Kickback & Authorization Controls",

    # -- Conflict-of-Interest & Ethics Controls --------------------------------
    "ny-mta-2020-patel": "Conflict-of-Interest & Ethics Controls",
    "ny-mta-2023-nepotism": "Conflict-of-Interest & Ethics Controls",

    # ===========================================================================
    # New Jersey and the Port Authority of NY & NJ
    # ===========================================================================

    # -- Procurement & Bid-Integrity Controls -----------------------------------
    "panynj-2017-crimson-vertuccio": "Procurement & Bid-Integrity Controls",       # concealed org-crime control to win the contract
    "nj-scc-2005-monahan-cm3-forgery": "Procurement & Bid-Integrity Controls",     # forged prequalification docs to win a contract
    "nj-egg-harbor-2023-charter-bidrig": "Procurement & Bid-Integrity Controls",   # split contract to evade bidding threshold
    "nj-westfield-2011-disko": "Procurement & Bid-Integrity Controls",            # engineer rigged/inflated bid quotes

    # -- MWBE/DBE & Professional-Certification Controls -------------------------
    "panynj-2016-dcm-erectors-mwbe": "MWBE/DBE & Professional-Certification Controls",
    "njdot-2022-abbonizio-direct-connection": "MWBE/DBE & Professional-Certification Controls",  # fraudulent DBE pass-through

    # -- Payroll, Timekeeping & Certified-Payroll Controls -----------------------
    "panynj-2016-padover-arbor-concrete": "Payroll, Timekeeping & Certified-Payroll Controls",  # false certified-payroll benefits
    "nj-hillsborough-2026-kickback": "Payroll, Timekeeping & Certified-Payroll Controls",        # inflated OT timesheets approved for kickbacks

    # -- Disbursement, Invoice & Change-Order Controls ---------------------------
    "panynj-2015-tishman-overbilling": "Disbursement, Invoice & Change-Order Controls",
    "panynj-2021-vja-overbilling": "Disbursement, Invoice & Change-Order Controls",
    "nj-scc-2005-ig-report": "Disbursement, Invoice & Change-Order Controls",       # lax payment/financial controls generally
    "nj-scc-2006-bana-edison-embezzlement": "Disbursement, Invoice & Change-Order Controls",
    "nj-scc-2006-rullo-megan-group": "Disbursement, Invoice & Change-Order Controls",
    "nj-sda-2021-sci-part2-oversight": "Disbursement, Invoice & Change-Order Controls",  # weak contractor/cost oversight

    # -- Bribery, Kickback & Authorization Controls ------------------------------
    "panynj-2016-samson-chairmans-flight": "Bribery, Kickback & Authorization Controls",
    "panynj-2019-wtc-hatzel-buehler": "Bribery, Kickback & Authorization Controls",
    "panynj-2023-newark-restroom-committee": "Bribery, Kickback & Authorization Controls",
    "panynj-2025-newark-restroom-vendor": "Bribery, Kickback & Authorization Controls",
    "njdot-2015-eagle-rock-metellus": "Bribery, Kickback & Authorization Controls",
    "njdot-2015-eagle-rock-dubose": "Bribery, Kickback & Authorization Controls",
    "njdot-2012-tarheel-routes1-9": "Bribery, Kickback & Authorization Controls",
    "drpa-2012-osc-capital-funds": "Bribery, Kickback & Authorization Controls",   # non-transparent kickback-like commissions
    "nj-hoboken-2010-cammarano": "Bribery, Kickback & Authorization Controls",
    "nj-jerseycity-2010-vega": "Bribery, Kickback & Authorization Controls",
    "nj-jerseycity-2010-beldini": "Bribery, Kickback & Authorization Controls",
    "nj-passaic-2016-blanco": "Bribery, Kickback & Authorization Controls",
    "nj-trenton-2014-mack": "Bribery, Kickback & Authorization Controls",
    "nj-newark-2026-garcia": "Bribery, Kickback & Authorization Controls",
    "nj-unioncity-2012-venegas": "Bribery, Kickback & Authorization Controls",

    # -- Conflict-of-Interest & Ethics Controls -----------------------------------
    "nj-sda-2020-sci-part1-patronage": "Conflict-of-Interest & Ethics Controls",   # nepotism/patronage hiring

    # -- Economic-Development & Tax-Incentive Controls (new category) -------------
    "nj-camden-2024-norcross-dismissed": "Economic-Development & Tax-Incentive Controls",
    "nj-camden-2024-holtec-taxcredit": "Economic-Development & Tax-Incentive Controls",

    # ===========================================================================
    # Cases from a later research review (27 new cases)
    # across NY OSC, NYC-area county DAs + DOI, NY DOL/IDA, NJ OSC, NJ county
    # prosecutors/DCJ, and NJ EDA/SCI. See build_dataset.py docstring additions.
    # ===========================================================================

    # -- Procurement & Bid-Integrity Controls --
    "ny-osc-monroecounty-bidrigging-2016": "Procurement & Bid-Integrity Controls",  # bid-rigging steered $311M in IT/security infrastructure contracts
    "ny-nassauda-2025-unger-lawrence-ufsd-hvac": "Procurement & Bid-Integrity Controls",  # fake emergency invoked to bypass competitive bidding
    "ny-amsterdam-2016-squires-ida": "Procurement & Bid-Integrity Controls",  # forged workers'-comp exemption forms to win IDA-sponsored bid
    "nj-meadowlands-2008-encap-gauger": "Procurement & Bid-Integrity Controls",  # misrepresented landfill-closure qualifications to win contract
    "nj-doc-2010-armstrong-kerth-alarmbidrig": "Procurement & Bid-Integrity Controls",  # rigged bids via solicited inflated cover bids
    "nj-sci-1999-school-roofing": "Procurement & Bid-Integrity Controls",  # secret spec-writing collusion with supplier steered contracts

    # -- MWBE/DBE & Professional-Certification Controls --
    "ny-osc-ogs-construction-mgmt-mwbe-2021": "MWBE/DBE & Professional-Certification Controls",  # WBE subcontracted all work to a non-MWBE to claim credit

    # -- Payroll, Timekeeping & Certified-Payroll Controls --
    "ny-brooklynda-2016-dayan-eec-nycha": "Payroll, Timekeeping & Certified-Payroll Controls",  # false certified payrolls hid wage theft on NYCHA capital rehab bid
    "ny-queensda-2022-singh-ps71": "Payroll, Timekeeping & Certified-Payroll Controls",  # foreman extorted per-day wage kickbacks from workers
    "ny-queensda-2020-deol-laser-electrical": "Payroll, Timekeeping & Certified-Payroll Controls",  # inflated reported wages, false certified payrolls
    "ny-suffolkda-2025-dealmeida-rl-concrete-longwood": "Payroll, Timekeeping & Certified-Payroll Controls",  # misclassified workers on certified payroll to underpay
    "ny-sdny-2025-joseph-bwk-uniondale": "Payroll, Timekeeping & Certified-Payroll Controls",  # falsified certified payroll on school construction contracts
    "ny-doe-2019-mangru": "Payroll, Timekeeping & Certified-Payroll Controls",  # false certified payrolls to underpay DOE renovation workers
    "ny-multi-2017-msr-riglietti": "Payroll, Timekeeping & Certified-Payroll Controls",  # false certified payrolls across SCA/OGS/MTA sites
    "ny-nycha-2022-lintech": "Payroll, Timekeeping & Certified-Payroll Controls",  # prevailing-wage theft on NYCHA scaffolding-electrical subcontracts
    "ny-cuny-2014-r3electrical": "Payroll, Timekeeping & Certified-Payroll Controls",  # false certified payrolls on CUNY/NYPA-funded projects

    # -- Disbursement, Invoice & Change-Order Controls --
    "nj-pvsc-2021-clark-roofing": "Disbursement, Invoice & Change-Order Controls",  # false equipment-rental billing on roofing contract
    "nj-scc-2009-parikh-clarktownship-doors": "Disbursement, Invoice & Change-Order Controls",  # false certification authorized improper payment claim

    # -- Bribery, Kickback & Authorization Controls --
    "ny-brooklynda-2015-elchoum-ama-ps138k": "Bribery, Kickback & Authorization Controls",  # cash bribes to SCA project officer to expedite payments
    "ny-hempstead-2024-bozier-vhha-bidrigging": "Bribery, Kickback & Authorization Controls",  # board chairman rigged bids, took kickbacks on capital repairs
    "ny-sca-2005-sixofficers-bribery": "Bribery, Kickback & Authorization Controls",  # SCA project officers bribed for payment approvals/bid data
    "nj-doc-2010-kennedy-stermer-capitalprojects": "Bribery, Kickback & Authorization Controls",  # official steered sub-threshold capital contracts for kickbacks
    "nj-sci-1971-point-breeze-jersey-city": "Bribery, Kickback & Authorization Controls",  # payoff to public officials on urban-renewal land sales

    # -- Conflict-of-Interest & Ethics Controls --
    "ny-osc-orangecounty-ida-corruption-2021": "Conflict-of-Interest & Ethics Controls",  # undisclosed conflicts of interest in IDA accelerator-program oversight
    "nj-sda-2010-murphy-hillinternational": "Conflict-of-Interest & Ethics Controls",  # undisclosed friendship with vendor VP steered contract selection
    "nj-chesterfield-2013-durr-tdr": "Conflict-of-Interest & Ethics Controls",  # official used board seat to advance own undisclosed land deal
    "nj-blairstown-2008-davis-municipalcomplex": "Conflict-of-Interest & Ethics Controls",  # committee chairman diverted funds via shell company

    # -- Cases from a later research review --
    'ny-dotoig-2011-eea-skanska-fulton-street': 'MWBE/DBE & Professional-Certification Controls',
    'ny-dotoig-2023-manotrees-sueperior': 'MWBE/DBE & Professional-Certification Controls',
    'ny-dotoig-2017-sanzo-willis-ave': 'MWBE/DBE & Professional-Certification Controls',
    'nj-dotoig-2024-mv-contracting': 'MWBE/DBE & Professional-Certification Controls',
    'ny-dotoig-2021-naughton-tappan-zee': 'MWBE/DBE & Professional-Certification Controls',
    'ny-dotoig-2008-loguidice-dbe': 'MWBE/DBE & Professional-Certification Controls',
    'njt-2024-ferrara-hblr': 'Payroll, Timekeeping & Certified-Payroll Controls',
    'ny-comptroller-2023-doe-sphinx-certifiedpayroll': 'Payroll, Timekeeping & Certified-Payroll Controls',
    'ny-dotoig-2025-intercounty-lizza': 'Payroll, Timekeeping & Certified-Payroll Controls',
    'ny-comptroller-2011-edc-turner-questionablepayments': 'Disbursement, Invoice & Change-Order Controls',
    'ny-comptroller-2012-doitt-hp-ectp-overbilling': 'Disbursement, Invoice & Change-Order Controls',
    'ny-comptroller-2024-nycha-contractor-repairs-audit': 'Disbursement, Invoice & Change-Order Controls',
    'panynj-2017-sec-roadway-bond-disclosure': 'Disbursement, Invoice & Change-Order Controls',
    'ny-nycha-2025-colon': 'Bribery, Kickback & Authorization Controls',
    'ny-nycha-2025-gilmore': 'Bribery, Kickback & Authorization Controls',
    'ny-nycha-2025-mercado': 'Bribery, Kickback & Authorization Controls',
    'ny-nycha-2023-gibbs': 'Bribery, Kickback & Authorization Controls',
    'ny-nycha-2023-figueroa': 'Bribery, Kickback & Authorization Controls',
    'ny-nycha-2021-microcontracts': 'Bribery, Kickback & Authorization Controls',
    'ny-dotoig-2009-afc-catapano': 'Bribery, Kickback & Authorization Controls',
    'sec-2016-united-chairmans-flight': 'Bribery, Kickback & Authorization Controls',
}

CATEGORY_ORDER = [
    "Procurement & Bid-Integrity Controls",
    "MWBE/DBE & Professional-Certification Controls",
    "Payroll, Timekeeping & Certified-Payroll Controls",
    "Disbursement, Invoice & Change-Order Controls",
    "Bribery, Kickback & Authorization Controls",
    "Conflict-of-Interest & Ethics Controls",
    "Economic-Development & Tax-Incentive Controls",
]

missing = [c["case_id"] for c in cases if c["case_id"] not in CONTROL_CATEGORY]
if missing:
    raise SystemExit(f"CONTROL_CATEGORY is missing {len(missing)} case(s): {missing}")


# ---------------------------------------------------------------------
# 2. Magnitude tier -- based on the case's own disclosed dollar_amount.
# ---------------------------------------------------------------------
def magnitude_tier(dollar_amount):
    if dollar_amount >= 1_000_000:
        return "High"
    if dollar_amount >= 100_000:
        return "Medium"
    if dollar_amount > 0:
        return "Low"
    return "Undisclosed"


for c in cases:
    c["control_category"] = CONTROL_CATEGORY[c["case_id"]]
    c["magnitude_tier"] = magnitude_tier(c["dollar_amount"])

# ---------------------------------------------------------------------
# 3. Pervasiveness -- how many unique cases share this case's
#    (agency_group, control_category) pair.
# ---------------------------------------------------------------------
pair_counts = Counter((c["agency_group"], c["control_category"]) for c in cases)


def pervasiveness(agency_group, control_category):
    n = pair_counts[(agency_group, control_category)]
    if n >= 3:
        return "Pervasive"
    if n == 2:
        return "Recurring"
    return "Isolated"


for c in cases:
    c["pervasiveness"] = pervasiveness(c["agency_group"], c["control_category"])


# ---------------------------------------------------------------------
# 4. Severity -- Material Weakness / Significant Deficiency / Control Deficiency.
# ---------------------------------------------------------------------
def severity(mag, perv):
    if mag == "High":
        return "Material Weakness"
    if mag == "Medium" and perv == "Pervasive":
        return "Material Weakness"
    if mag == "Medium":
        return "Significant Deficiency"
    if perv in ("Pervasive", "Recurring"):
        return "Significant Deficiency"
    return "Control Deficiency"


for c in cases:
    c["severity"] = severity(c["magnitude_tier"], c["pervasiveness"])

# ---------------------------------------------------------------------
# 5. Aggregates
# ---------------------------------------------------------------------
def counted_amount(c):
    return c["dollar_amount"] if c["count_in_dollar_total"] else 0


by_category = []
for cat in CATEGORY_ORDER:
    rows = [c for c in cases if c["control_category"] == cat]
    by_category.append({
        "control_category": cat,
        "case_count": len(rows),
        "dollar_exposure": sum(counted_amount(c) for c in rows),
        "material_weakness_count": sum(1 for c in rows if c["severity"] == "Material Weakness"),
    })

SEVERITY_ORDER = ["Material Weakness", "Significant Deficiency", "Control Deficiency"]
severity_summary = []
total_cases = len(cases)
total_exposure = sum(counted_amount(c) for c in cases)
for sev in SEVERITY_ORDER:
    rows = [c for c in cases if c["severity"] == sev]
    exposure = sum(counted_amount(c) for c in rows)
    severity_summary.append({
        "severity": sev,
        "case_count": len(rows),
        "case_pct": round(100 * len(rows) / total_cases, 1),
        "dollar_exposure": exposure,
        "dollar_pct": round(100 * exposure / total_exposure, 1) if total_exposure else 0,
    })

pervasive_pairs = sorted(
    [{"agency_group": a, "control_category": cat, "case_count": n}
     for (a, cat), n in pair_counts.items() if n >= 3],
    key=lambda r: -r["case_count"],
)

with open("data/cases_with_controls.json", "w") as f:
    json.dump(cases, f, indent=2)

with open("data/controls_by_category.json", "w") as f:
    json.dump(by_category, f, indent=2)

with open("data/severity_summary.json", "w") as f:
    json.dump({
        "by_severity": severity_summary,
        "total_cases": total_cases,
        "total_exposure": total_exposure,
        "pervasive_agency_category_pairs": pervasive_pairs,
    }, f, indent=2)

print("Control category (case_count / dollar_exposure / material weaknesses):")
for row in by_category:
    print(f"  {row['control_category']:<55} {row['case_count']:>3}  ${row['dollar_exposure']:>13,}  MW={row['material_weakness_count']}")

print("\nSeverity distribution:")
for row in severity_summary:
    print(f"  {row['severity']:<25} {row['case_count']:>3} ({row['case_pct']}%)  ${row['dollar_exposure']:>13,} ({row['dollar_pct']}%)")

print(f"\nPervasive (agency, control category) pairs (>=3 cases): {len(pervasive_pairs)}")
for row in pervasive_pairs:
    print(f"  {row['agency_group']} x {row['control_category']}: {row['case_count']} cases")

with open("data/summary.json") as f:
    _summary = json.load(f)
_summary_total = _summary["dollar_exposure"]["total_exposure_counted"]
assert total_exposure == _summary_total, (
    f"Total exposure {total_exposure} does not tie to summary.json's {_summary_total}"
)
print(f"\nOK: total dollar exposure (${total_exposure:,}) ties to data/summary.json.")
