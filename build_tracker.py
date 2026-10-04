"""
build_tracker.py -- builds the interactive tracker, "NYNJ Capital Risk
Data": a case register with filters, a map, charts, a disclosed risk
indicator, and state-specific narrative sections, all precomputed at
build time.

Nothing on the page makes a live model call. Every case's fraud-mechanism
archetype, red flags, and verification-gap note come from
data/ai_typology.json, computed once ahead of time by reading each case's
own cited source -- not from a button a visitor clicks. The only runtime
capability the page declares is `db`, used for a visitor's personal
review-status tracker (Unreviewed / Flagged / Cleared); nothing else is
stored or sent anywhere.

The page also includes:
  - a disclosed, rule-based risk indicator (data/risk_index.json, built by
    risk_index.py): which agency/control-category pairings are "Elevated
    Focus," "Recurring Pattern," or "Isolated Precedent," framed as
    audit-planning guidance, not a fraud prediction.
  - "What this means for New York / New Jersey" sections (data/
    state_narratives.json, built by state_narratives.py), plus a short
    note on the bi-state Port Authority.
  - a static methodology note explaining how the classification was done.

Reads data/cases_with_controls.json, data/ai_typology.json,
data/risk_index.json, data/state_narratives.json, data/summary.json, and
data/severity_summary.json. Writes capital_risk_tracker.html.
"""

import json
import re

with open("data/cases_with_controls.json") as f:
    RAW_CASES = json.load(f)
with open("data/ai_typology.json") as f:
    TYPOLOGY = {t["case_id"]: t for t in json.load(f)}
with open("data/risk_index.json") as f:
    RISK_INDEX = json.load(f)
with open("data/state_narratives.json") as f:
    STATE_NARRATIVES = json.load(f)
with open("data/summary.json") as f:
    SUMMARY = json.load(f)
with open("data/severity_summary.json") as f:
    SEVERITY_SUMMARY = json.load(f)


def esc(s):
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def md_em(s):
    """*word* -> <em>word</em>, and normalize ' -- ' to an em dash, for the
    narrative prose pulled in from state_narratives.json."""
    s = s.replace(" -- ", " — ")
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    return s


def money(n):
    n = n or 0
    neg = n < 0
    n = abs(n)
    if n >= 1_000_000:
        v = n / 1_000_000
        if n % 1_000_000 == 0:
            s = f"${int(n // 1_000_000)}M"
        else:
            s = f"${v:.1f}M"
    elif n >= 1_000:
        s = f"${round(n/1000)}K"
    else:
        s = f"${n:.0f}"
    return ("-" if neg else "") + s


def fnum(x):
    """1-decimal float formatted without a trailing .0"""
    return f"{x:g}"


CAT_ABBR = {
    "Procurement & Bid-Integrity Controls": "Procurement & bid integrity",
    "MWBE/DBE & Professional-Certification Controls": "MWBE/DBE & certification",
    "Payroll, Timekeeping & Certified-Payroll Controls": "Payroll & certified payroll",
    "Disbursement, Invoice & Change-Order Controls": "Disbursement & invoice",
    "Bribery, Kickback & Authorization Controls": "Bribery & authorization",
    "Conflict-of-Interest & Ethics Controls": "Conflict of interest",
    "Economic-Development & Tax-Incentive Controls": "Economic dev. & tax incentive",
}

RISK_TIER_CLASS = {
    "Elevated Focus": "elevated",
    "Recurring Pattern": "recurring",
    "Isolated Precedent": "isolated",
}

# ---------------------------------------------------------------------
# Build the case list: same schema the tracker has always used, plus the
# precomputed typology and risk-tier fields baked in.
# ---------------------------------------------------------------------
RISK_LOOKUP = {(r["agency_group"], r["control_category"]): r for r in RISK_INDEX}

CASES = []
for c in RAW_CASES:
    if c.get("is_duplicate"):
        continue
    t = TYPOLOGY.get(c["case_id"])
    if t is None:
        raise SystemExit(f"missing ai_typology.json entry for {c['case_id']}")
    pair = RISK_LOOKUP.get((c["agency_group"], c["control_category"]))
    if pair is None:
        raise SystemExit(f"missing risk_index.json pair for {c['case_id']}")
    CASES.append({
        "id": c["case_id"],
        "state": c["state"],
        "date": c["date"].split("T")[0],
        "year": c["year"],
        "region": c["region_group"],
        "agency": c["agency_group"],
        "type": c["project_type"],
        "category": c["control_category"],
        "severity": c["severity"],
        "magnitude": c["magnitude_tier"],
        "pervasiveness": c["pervasiveness"],
        "verification": c["verification_class"],
        "amount": c["dollar_amount"],
        "counted": c["count_in_dollar_total"],
        "basis": c["dollar_amount_basis"],
        "entities": c["entities"],
        "title": c["title"],
        "summary": c["summary"],
        "violation": c["violation_type"],
        "url": c["source_url"],
        "source": c["citing_source"],
        "corroboration": c["corroboration_note"],
        "scheme": c["scheme_family"],
        "stage": c["stage_bucket"],
        "archetype": t["archetype"],
        "red_flags": t["red_flags"],
        "verification_gap": t["verification_gap"],
        "confidence": t["confidence"],
        "risk_tier": pair["risk_tier"],
        "risk_pair_count": pair["case_count"],
        "risk_recency": pair["recency_share"],
        "risk_recent_window": pair["recent_window"],
    })

_expected_n = SUMMARY["verification"]["n_unique_cases"]
assert len(CASES) == _expected_n, f"expected {_expected_n} cases in the tracker (per data/summary.json), got {len(CASES)}"

META = {
    "n_cases": SUMMARY["verification"]["n_unique_cases"],
    "n_raw": SUMMARY["verification"]["n_raw_records"],
    "dup_rate": SUMMARY["verification"]["duplicate_rate_pct"],
    "confirmed_pct": SUMMARY["verification"]["confirmed_pct"],
    "total_exposure": SUMMARY["dollar_exposure"]["total_exposure_counted"],
    "regions": SUMMARY["region_count"],
    "agencies": SUMMARY["agency_count"],
    "by_state": SUMMARY["by_state"],
    "severity_summary": SEVERITY_SUMMARY,
}

CASE_DATA_JSON = json.dumps({"cases": CASES, "meta": META}, separators=(",", ":"))

# ---------------------------------------------------------------------
# Static "Risk indicator" table (agency x control-category pairs)
# ---------------------------------------------------------------------
def risk_row_html(r):
    return (
        "<tr><td>" + esc(r["agency_group"]) + "</td>"
        "<td>" + esc(CAT_ABBR.get(r["control_category"], r["control_category"])) + "</td>"
        '<td class="tnum">' + str(r["case_count"]) + "</td>"
        '<td class="tnum">' + esc(money(r["dollar_exposure"])) + "</td>"
        '<td class="tnum">' + f"{round(r['recency_share']*100)}%" + "</td>"
        "<td>" + esc(", ".join(r["states"])) + "</td>"
        '<td><span class="risk-tier ' + RISK_TIER_CLASS[r["risk_tier"]] + '">'
        + esc(r["risk_tier"]) + "</span></td></tr>"
    )


_non_isolated = [r for r in RISK_INDEX if r["risk_tier"] != "Isolated Precedent"]
_isolated = [r for r in RISK_INDEX if r["risk_tier"] == "Isolated Precedent"]
_tier_order = {"Elevated Focus": 0, "Recurring Pattern": 1}
_non_isolated.sort(key=lambda r: (_tier_order[r["risk_tier"]], -r["dollar_exposure"]))
_isolated.sort(key=lambda r: -r["dollar_exposure"])

RISK_TABLE_MAIN = "".join(risk_row_html(r) for r in _non_isolated)
RISK_TABLE_ISOLATED = "".join(risk_row_html(r) for r in _isolated)
N_ELEVATED = sum(1 for r in RISK_INDEX if r["risk_tier"] == "Elevated Focus")
N_RECURRING = sum(1 for r in RISK_INDEX if r["risk_tier"] == "Recurring Pattern")
N_ISOLATED = len(_isolated)

RISK_SECTION_HTML = f'''
  <section id="risk-section">
    <div class="section-head"><h2>Risk indicator &middot; agency &times; control category</h2><span class="hint">A disclosed, non-predictive rubric &mdash; not a forecast</span></div>
    <div class="card" style="padding:18px 18px 20px;">
      <p class="risk-note">Each agency &times; control-category pairing gets a <b>risk_tier</b> from three fixed signals: <b>pervasiveness</b> (case count), whether it has a <b>Material Weakness</b> case, and <b>recency</b> (share of cases in the last 10 years, {esc(_non_isolated[0]["recent_window"]) if _non_isolated else ""}). &ldquo;Elevated Focus&rdquo; meets all three. No model is involved. <b>This is not a prediction</b> &mdash; it shows where scrutiny has concentrated historically, not an unbiased base rate.</p>
      <div class="risk-table-wrap">
        <table class="risk-table">
          <thead><tr><th>Agency</th><th>Control category</th><th class="tnum">Cases</th><th class="tnum">Exposure</th><th class="tnum">Recent</th><th>States</th><th>Risk tier</th></tr></thead>
          <tbody>{RISK_TABLE_MAIN}</tbody>
        </table>
      </div>
      <details class="risk-toggle">
        <summary>+ {N_ISOLATED} additional isolated-precedent pairings (one matching case each)</summary>
        <div class="risk-table-wrap" style="margin-top:10px;">
          <table class="risk-table">
            <thead><tr><th>Agency</th><th>Control category</th><th class="tnum">Cases</th><th class="tnum">Exposure</th><th class="tnum">Recent</th><th>States</th><th>Risk tier</th></tr></thead>
            <tbody>{RISK_TABLE_ISOLATED}</tbody>
          </table>
        </div>
      </details>
    </div>
  </section>
'''

# ---------------------------------------------------------------------
# Static "What this means for New York / New Jersey" narrative section
# ---------------------------------------------------------------------
def narrative_card_html(block, css_class=""):
    ks = block["key_stats"]
    stats = [
        f'<span class="narrative-stat"><b>{ks["case_count"]}</b> cases</span>',
        f'<span class="narrative-stat"><b>{esc(money(ks["dollar_exposure"]))}</b> exposure</span>',
        f'<span class="narrative-stat"><b>{fnum(ks["confirmed_pct"])}%</b> confirmed</span>',
        f'<span class="narrative-stat"><b>{fnum(ks["material_weakness_pct"])}%</b> material weakness</span>',
    ]
    if "elevated_focus_count" in ks:
        stats.append(f'<span class="narrative-stat"><b>{ks["elevated_focus_count"]}</b> elevated-focus pair(s)</span>')
    paras = block["paragraphs"]
    if len(paras) > 1:
        body_paras, caveat = paras[:-1], paras[-1]
    else:
        body_paras, caveat = paras, None
    html = f'<div class="card narrative-card {css_class}"><h3>{esc(block["heading"])}</h3>'
    html += '<div class="stat-row">' + "".join(stats) + "</div>"
    for p in body_paras:
        html += "<p>" + md_em(esc(p)) + "</p>"
    if caveat:
        html += '<p class="narrative-caveat">' + md_em(esc(caveat)) + "</p>"
    html += "</div>"
    return html


NARRATIVE_SECTION_HTML = f'''
  <section id="narrative-section">
    <div class="section-head"><h2>What this means for New York &amp; New Jersey</h2><span class="hint">Grounded in the register&rsquo;s own per-state breakdowns &mdash; each panel repeats its own caveat</span></div>
    <div class="narrative-grid">
      {narrative_card_html(STATE_NARRATIVES["NY"])}
      {narrative_card_html(STATE_NARRATIVES["NJ"])}
    </div>
    {narrative_card_html(STATE_NARRATIVES["NY/NJ"], "narrative-crossborder")}
  </section>
'''

# ---------------------------------------------------------------------
# HTML assembly
# ---------------------------------------------------------------------
HEAD = '''<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}html{scroll-padding-top:env(safe-area-inset-top,0px)}body{margin:0;padding:0;font:14px 'Times New Roman',Times,serif;background:#ffffff;color:#141413}img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style></head><body>
<title>NYNJ Capital Risk Data</title>
<style>
/* Layout concept: institutional / audit-workpaper register -- compact cover-sheet header with a
   ticker-style stat strip -> where-the-cases-are map (muted basemap, colored nodes) -> filter
   panel of flat outline tags -> 4-up exhibits -> a dense case register (table, not cards) with
   an expandable per-case review row -> a static risk-indicator table -> static NY/NJ narrative
   sections. Flat surfaces, hairline rules, no drop shadow. Map, charts, and the register all
   recompute from the currently filtered case set; the risk-indicator table and the NY/NJ
   narrative are dataset-wide and don't change with the filters. */
:root{
  --bg:#ffffff; --surface:#ffffff; --surface-2:#f2f2f2;
  --ink:#14130f; --ink-2:#4b4a44; --ink-3:#84827a; --rule:#dcdcdc;
  --navy:#0f1a2b; --navy-ink:#f3f1e9;
  --blue:#2a78d6; --orange:#eb6834; --aqua:#1baf7a;
  --good:#0ca30c; --warning:#a96a00; --serious:#c1512e;
  --ai:#6d49c4;
  --radius:3px; --radius-lg:4px;
  --font-display:'Times New Roman',Times,Georgia,serif;
  --font-body:'Times New Roman',Times,Georgia,serif;
  --font-mono:'Times New Roman',Times,Georgia,serif;
}
/* Dark-mode auto-switch intentionally removed: this page always renders the light/white
   palette above, regardless of the viewer's OS or browser color-scheme setting. */
*{box-sizing:border-box;}
body{background:var(--bg); color:var(--ink); font-family:var(--font-body); padding-inline:0;}
.wrap{max-width:1180px; margin:0 auto; padding:0 20px 64px;}
a{color:var(--blue);}
h1,h2,h3{font-family:var(--font-display); font-weight:600; text-wrap:balance; margin:0;}
.mono{font-family:var(--font-mono);}
.tnum{font-variant-numeric:tabular-nums;}
button{font-family:inherit; cursor:pointer;}
::selection{background:color-mix(in srgb, var(--blue) 30%, transparent);}

/* ---------- header ---------- */
.hero{background:var(--surface); color:var(--ink); border-bottom:1px solid var(--rule);}
.hero .wrap{padding-top:24px; padding-bottom:0;}
.hero-top{display:flex; align-items:baseline; justify-content:space-between; gap:14px; flex-wrap:wrap; margin-bottom:14px;}
.eyebrow{font-family:var(--font-mono); font-size:10.5px; letter-spacing:.09em; text-transform:uppercase; color:var(--ink-3);}
.hero-actions{display:flex; gap:14px; align-items:baseline; font-family:var(--font-mono); font-size:11px;}
.hero-actions a{color:var(--ink-2);}
.hero-actions a:hover{color:var(--ink);}
.hero-actions span{color:var(--ink-3);}
.hero h1{font-size:clamp(22px,3.2vw,30px); line-height:1.14;}
.hero p{margin:9px 0 0; max-width:70ch; color:var(--ink-2); line-height:1.55; font-size:13.5px;}
.stat-strip{display:flex; flex-wrap:wrap; margin-top:22px; border-top:1px solid var(--rule);}
.stat-cell{flex:1 1 140px; padding:13px 18px; border-right:1px solid var(--rule); border-bottom:1px solid var(--rule);}
.stat-cell:last-child{border-right:none;}
.stat-cell .n{font-family:var(--font-mono); font-weight:600; font-size:18px; letter-spacing:-.01em;}
.stat-cell .l{font-size:10px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-3); margin-top:4px; line-height:1.35;}

/* ---------- section shell ---------- */
section{padding:26px 0;}
.section-head{display:flex; align-items:baseline; justify-content:space-between; gap:12px; margin-bottom:12px; flex-wrap:wrap;}
.section-head h2{font-size:15px; letter-spacing:.01em;}
.section-head .hint{color:var(--ink-3); font-size:11.5px; font-family:var(--font-mono);}
.card{background:var(--surface); border:1px solid var(--rule); border-radius:var(--radius-lg);}

/* ---------- map ---------- */
.map-wrap{display:flex; gap:22px; padding:18px; flex-wrap:wrap;}
.map-svg-wrap{flex:0 0 auto; width:260px; max-width:100%;}
.map-svg-wrap svg{width:100%; height:auto; display:block; overflow:visible;}
.map-bg-ny{fill:color-mix(in srgb, var(--blue) 6%, var(--surface)); stroke:color-mix(in srgb, var(--blue) 22%, var(--rule)); stroke-width:1;}
.map-bg-li{fill:color-mix(in srgb, var(--blue) 6%, var(--surface)); stroke:color-mix(in srgb, var(--blue) 22%, var(--rule)); stroke-width:1;}
.map-bg-nj{fill:color-mix(in srgb, var(--orange) 6%, var(--surface)); stroke:color-mix(in srgb, var(--orange) 22%, var(--rule)); stroke-width:1;}
.map-region-label{font-family:var(--font-mono); font-size:8.5px; letter-spacing:.09em; fill:var(--ink-3); text-anchor:middle;}
.map-node{cursor:pointer;}
.map-node circle{transition:fill-opacity .12s ease, stroke-width .12s ease; stroke:var(--surface); stroke-width:1.5;}
.map-node:hover circle{fill-opacity:.8 !important;}
.map-node.selected circle{stroke:var(--ink); stroke-width:2.5;}
.map-node .node-count{font-family:var(--font-mono); font-weight:700; fill:#fff; text-anchor:middle; pointer-events:none;}
.map-node .node-label{font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.03em; fill:var(--ink-3); text-anchor:middle; pointer-events:none;}
.map-side{flex:1 1 200px; min-width:190px; display:flex; flex-direction:column; gap:12px; justify-content:center;}
.map-legend{display:flex; flex-direction:column; gap:6px; font-size:11.5px; color:var(--ink-2);}
.map-legend-item{display:flex; align-items:center; gap:8px;}
.map-legend-item i{width:9px; height:9px; border-radius:1px; display:inline-block; flex:0 0 auto; background:var(--surface-2); border:1px solid var(--rule);}
.map-legend-item i.ring{background:none; border:2px solid var(--aqua);}
.map-chips{display:flex; flex-wrap:wrap; gap:6px;}
.map-chip{border:1px solid var(--rule); background:transparent; color:var(--ink-2); border-radius:var(--radius); padding:4px 9px; font-size:10.5px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.02em;}
.map-chip[aria-pressed="true"]{background:var(--ink); border-color:var(--ink); color:var(--surface);}
.map-hint{font-size:11px; color:var(--ink-3); line-height:1.5; margin:0;}
@media (max-width:640px){ .map-wrap{justify-content:center; text-align:center;} .map-side{align-items:center;} }

/* ---------- filters ---------- */
.filters{padding:18px 18px 16px; display:flex; flex-direction:column; gap:14px;}
.search-row{display:flex; gap:10px; flex-wrap:wrap;}
.search-row input[type="search"]{flex:1 1 240px; min-width:0; padding:8px 11px; border-radius:var(--radius); border:1px solid var(--rule); background:var(--bg); color:var(--ink); font-size:13px; font-family:var(--font-body);}
.chip-group{display:flex; flex-wrap:wrap; gap:6px; align-items:center;}
.chip-group .gl{font-size:10px; letter-spacing:.07em; text-transform:uppercase; color:var(--ink-3); font-family:var(--font-mono); margin-right:2px; flex:0 0 auto;}
.chip{border:1px solid var(--rule); background:transparent; color:var(--ink-2); border-radius:var(--radius); padding:4px 10px; font-size:11px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.02em; line-height:1.3; white-space:nowrap;}
.chip[aria-pressed="true"]{background:var(--ink); border-color:var(--ink); color:var(--surface);}
.chip.sev-mw[aria-pressed="true"]{background:var(--serious); border-color:var(--serious); color:#fff;}
.chip.sev-sd[aria-pressed="true"]{background:var(--warning); border-color:var(--warning); color:#fff;}
.chip.sev-cd[aria-pressed="true"]{background:var(--good); border-color:var(--good); color:#fff;}
.chip.ver-c[aria-pressed="true"]{background:var(--good); border-color:var(--good); color:#fff;}
.chip.ver-p[aria-pressed="true"]{background:var(--warning); border-color:var(--warning); color:#fff;}
.chip.ver-u[aria-pressed="true"]{background:var(--serious); border-color:var(--serious); color:#fff;}
.chip.st-ny[aria-pressed="true"]{background:var(--blue); border-color:var(--blue); color:#fff;}
.chip.st-nj[aria-pressed="true"]{background:var(--orange); border-color:var(--orange); color:#fff;}
.chip.st-bi[aria-pressed="true"]{background:var(--aqua); border-color:var(--aqua); color:#04231a;}
.select-row{display:flex; flex-wrap:wrap; gap:10px;}
.select-row label{display:flex; flex-direction:column; gap:4px; font-size:10px; color:var(--ink-3); font-family:var(--font-mono); letter-spacing:.04em; text-transform:uppercase; flex:1 1 150px; min-width:130px;}
.select-row select, .select-row input[type="number"]{padding:7px 9px; border-radius:var(--radius); border:1px solid var(--rule); background:var(--bg); color:var(--ink); font-size:12.5px; font-family:var(--font-body);}
.filters-foot{display:flex; justify-content:flex-end;}
.btn-reset{background:none; border:1px solid var(--rule); color:var(--ink-2); border-radius:var(--radius); padding:6px 11px; font-size:11px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.03em;}
.btn-reset:hover{border-color:var(--ink-3);}

/* ---------- charts ---------- */
.chart-grid{display:grid; grid-template-columns:repeat(2,1fr); gap:12px;}
.chart-card{padding:14px 16px 12px;}
.chart-card h3{font-size:10.5px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.04em; font-weight:600; color:var(--ink-2); margin-bottom:10px;}
.chart-card svg{width:100%; height:auto; display:block;}
.chart-empty{color:var(--ink-3); font-size:12.5px; padding:20px 0; text-align:center;}
@media (max-width:860px){ .chart-grid{grid-template-columns:1fr;} }

/* ---------- toolbar ---------- */
.toolbar{display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px;}
.toolbar .count{font-size:12px; color:var(--ink-2); font-family:var(--font-mono);}
.toolbar .count b{color:var(--ink); font-family:var(--font-mono);}
.sort-control{display:flex; align-items:center; gap:6px; font-size:11px; color:var(--ink-3); font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.03em;}
.sort-control select{padding:6px 8px; border-radius:var(--radius); border:1px solid var(--rule); background:var(--surface); color:var(--ink); font-size:12px; font-family:var(--font-body); text-transform:none; letter-spacing:0;}

/* ---------- tags (compact, used in the register and detail panel) ---------- */
.tag{display:inline-block; padding:2px 6px; border-radius:2px; font-size:10px; font-weight:600; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.02em; border:1px solid transparent; white-space:nowrap;}
.tag-cat{color:var(--ink-2); border-color:var(--rule); background:var(--surface-2);}
.tag-mw{color:var(--serious); border-color:color-mix(in srgb, var(--serious) 45%, transparent); background:color-mix(in srgb, var(--serious) 8%, var(--surface));}
.tag-sd{color:var(--warning); border-color:color-mix(in srgb, var(--warning) 45%, transparent); background:color-mix(in srgb, var(--warning) 8%, var(--surface));}
.tag-cd{color:var(--good); border-color:color-mix(in srgb, var(--good) 45%, transparent); background:color-mix(in srgb, var(--good) 8%, var(--surface));}
.tag-ver-c{color:var(--good); border-color:color-mix(in srgb, var(--good) 40%, transparent);}
.tag-ver-p{color:var(--warning); border-color:color-mix(in srgb, var(--warning) 40%, transparent);}
.tag-ver-u{color:var(--serious); border-color:color-mix(in srgb, var(--serious) 40%, transparent);}
.tag-st-ny{color:var(--blue); border-color:color-mix(in srgb, var(--blue) 45%, transparent); background:color-mix(in srgb, var(--blue) 8%, var(--surface));}
.tag-st-nj{color:var(--orange); border-color:color-mix(in srgb, var(--orange) 45%, transparent); background:color-mix(in srgb, var(--orange) 8%, var(--surface));}
.tag-st-bi{color:#0d7a52; border-color:color-mix(in srgb, var(--aqua) 45%, transparent); background:color-mix(in srgb, var(--aqua) 10%, var(--surface));}
.tag-ai{color:var(--ai); border-color:color-mix(in srgb, var(--ai) 45%, transparent); background:color-mix(in srgb, var(--ai) 8%, var(--surface));}

/* ---------- case register (table) ---------- */
.table-wrap{overflow-x:auto; border:1px solid var(--rule); border-radius:var(--radius-lg); background:var(--surface);}
.case-table{width:100%; border-collapse:collapse; font-size:12px;}
.case-table thead th{position:sticky; top:0; background:var(--surface); text-align:left; font-family:var(--font-mono); font-size:9.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-3); font-weight:600; padding:9px 10px; border-bottom:1px solid var(--rule); white-space:nowrap;}
.case-table th.c-amount, .case-table td.c-amount{text-align:right;}
.case-table td{padding:9px 10px; border-bottom:1px solid var(--rule); vertical-align:middle;}
.case-row{cursor:pointer; -webkit-tap-highlight-color:transparent;}
.case-row:hover td{background:var(--surface-2);}
.case-row .c-date{font-family:var(--font-mono); font-size:11px; color:var(--ink-2); white-space:nowrap;}
.case-row .c-agency{font-weight:600; font-size:12.3px; min-width:150px;}
.case-row .c-agency small{display:block; font-weight:400; color:var(--ink-3); font-size:10.5px; margin-top:1px;}
.case-row .c-region{color:var(--ink-2); white-space:nowrap; font-size:11.5px;}
.case-row .c-amount{font-family:var(--font-mono); font-weight:600; white-space:nowrap;}
.case-row .c-rev{width:14px;}
.review-dot{width:8px; height:8px; border-radius:1px; display:inline-block; border:1px solid var(--rule);}
.review-dot.unreviewed{background:var(--ink-3); opacity:.35;}
.review-dot.flagged{background:var(--warning); border-color:var(--warning);}
.review-dot.cleared{background:var(--good); border-color:var(--good);}
.case-row .c-chev{width:14px; color:var(--ink-3); transition:transform .12s ease;}
.case-row[data-open="true"] .c-chev{transform:rotate(90deg);}
.case-row[data-open="true"] td{background:var(--surface-2);}
.case-detail-row{display:none;}
.case-row[data-open="true"] + .case-detail-row{display:table-row;}
.case-detail-row td{padding:0; border-bottom:1px solid var(--rule); background:var(--surface-2);}
.case-detail{padding:16px 18px 18px;}
.case-detail h4{font-family:var(--font-display); font-weight:600; font-size:14.5px; margin:0 0 6px;}
.case-detail p{margin:0 0 12px; font-size:12.8px; line-height:1.58; color:var(--ink-2); max-width:86ch;}
.meta-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px 18px; margin:10px 0 14px; font-size:12px;}
.meta-grid dt{font-family:var(--font-mono); font-size:9.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-3); margin:0;}
.meta-grid dd{margin:2px 0 0; color:var(--ink);}
.source-line{font-size:11.5px; color:var(--ink-3); margin-bottom:14px;}
.review-box{border:1px solid var(--rule); border-radius:var(--radius); padding:12px 14px; background:var(--surface);}
.review-box .rb-head{display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-bottom:8px;}
.review-box .rb-title{font-family:var(--font-mono); font-size:10px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-3);}
.status-btns{display:flex; gap:6px;}
.status-btn{border:1px solid var(--rule); background:var(--bg); color:var(--ink-2); border-radius:var(--radius); padding:5px 10px; font-size:11px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.02em;}
.status-btn[aria-pressed="true"].s-flagged{background:var(--warning); border-color:var(--warning); color:#1a1200;}
.status-btn[aria-pressed="true"].s-cleared{background:var(--good); border-color:var(--good); color:#fff;}
.status-btn[aria-pressed="true"].s-unreviewed{background:var(--ink-3); border-color:var(--ink-3); color:#fff;}
.review-box textarea{width:100%; min-height:52px; margin-top:8px; border:1px solid var(--rule); border-radius:var(--radius); padding:8px 10px; font-size:12.5px; font-family:var(--font-body); background:var(--bg); color:var(--ink); resize:vertical;}
.review-meta{font-size:10.5px; color:var(--ink-3); margin-top:6px; font-family:var(--font-mono);}
.readonly-note{font-size:11px; color:var(--serious); margin-top:6px; display:none;}
.readonly-note.show{display:block;}
.empty-state{text-align:center; padding:40px 20px; color:var(--ink-3);}
.empty-state button{margin-top:10px;}

/* ---------- precomputed fraud-typology block (per-case, static) ---------- */
.ai-block{border:1px dashed color-mix(in srgb, var(--ai) 45%, var(--rule)); border-radius:var(--radius); padding:12px 14px; margin-top:12px; background:color-mix(in srgb, var(--ai) 4%, var(--surface));}
.ai-block .rb-head{display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-bottom:8px;}
.ai-block .rb-title{font-family:var(--font-mono); font-size:10px; text-transform:uppercase; letter-spacing:.05em; color:var(--ai);}
.ai-flags{margin:8px 0 0; padding:0; list-style:none; display:flex; flex-direction:column; gap:4px;}
.ai-flags li{font-size:12px; color:var(--ink-2); padding-left:14px; position:relative; line-height:1.5;}
.ai-flags li::before{content:"—"; position:absolute; left:0; color:var(--ai);}
.ai-gap{font-size:12.3px; color:var(--ink); margin:10px 0 0; line-height:1.55;}
.ai-gap b{font-family:var(--font-mono); font-size:9.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-3); font-weight:600; display:block; margin-bottom:2px;}
.ai-disclaimer{font-size:10.5px; color:var(--ink-3); margin-top:10px; font-style:italic; line-height:1.5;}
.ai-case-meta{font-size:10.5px; color:var(--ink-3); margin-top:8px; font-family:var(--font-mono);}
.case-risk-context{font-size:11.5px; color:var(--ink-2); margin-top:10px; padding:8px 10px; border-radius:var(--radius); background:var(--surface); border:1px solid var(--rule); line-height:1.5;}

/* ---------- risk indicator ---------- */
.risk-note{font-size:12.3px; color:var(--ink-2); line-height:1.62; margin:0 0 14px; max-width:88ch;}
.risk-table-wrap{overflow-x:auto; border:1px solid var(--rule); border-radius:var(--radius-lg); background:var(--surface);}
.risk-table{width:100%; border-collapse:collapse; font-size:12px;}
.risk-table th{position:sticky; top:0; background:var(--surface); text-align:left; font-family:var(--font-mono); font-size:9.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-3); font-weight:600; padding:8px 10px; border-bottom:1px solid var(--rule); white-space:nowrap;}
.risk-table td{padding:8px 10px; border-bottom:1px solid var(--rule); vertical-align:middle;}
.risk-tier{display:inline-block; padding:2px 7px; border-radius:2px; font-size:9.5px; font-weight:700; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.03em; white-space:nowrap;}
.risk-tier.elevated{background:color-mix(in srgb, var(--serious) 14%, var(--surface)); color:var(--serious); border:1px solid color-mix(in srgb, var(--serious) 45%, transparent);}
.risk-tier.recurring{background:color-mix(in srgb, var(--warning) 14%, var(--surface)); color:var(--warning); border:1px solid color-mix(in srgb, var(--warning) 45%, transparent);}
.risk-tier.isolated{background:var(--surface-2); color:var(--ink-3); border:1px solid var(--rule);}
.risk-toggle{margin-top:14px; font-size:12px; color:var(--ink-2);}
.risk-toggle summary{cursor:pointer; font-family:var(--font-mono); font-size:11px; text-transform:uppercase; letter-spacing:.03em; color:var(--ink-3); padding:4px 0;}
.risk-toggle summary:hover{color:var(--ink);}

/* ---------- state narrative sections ---------- */
.narrative-grid{display:grid; grid-template-columns:1fr 1fr; gap:16px;}
.narrative-card{padding:18px 20px;}
.narrative-card h3{font-size:15px; margin-bottom:10px;}
.narrative-card p{font-size:12.6px; line-height:1.62; color:var(--ink-2); margin:0 0 11px;}
.narrative-card p:last-child{margin-bottom:0;}
.narrative-card .stat-row{display:flex; flex-wrap:wrap; gap:8px 18px; margin-bottom:14px; padding-bottom:14px; border-bottom:1px solid var(--rule);}
.narrative-stat{font-family:var(--font-mono); font-size:11px; color:var(--ink-2);}
.narrative-stat b{color:var(--ink); font-size:13.5px;}
.narrative-caveat{font-size:11px; color:var(--ink-3); font-style:italic; border-top:1px solid var(--rule); padding-top:11px; margin-top:2px;}
.narrative-crossborder{margin-top:16px;}
@media (max-width:860px){ .narrative-grid{grid-template-columns:1fr;} }

/* ---------- typology methodology (static) ---------- */
.ai-panel{padding:18px;}
.ai-intro{margin:0 0 4px; font-size:12.8px; color:var(--ink-2); line-height:1.58; max-width:78ch;}

/* ---------- footer ---------- */
footer{border-top:1px solid var(--rule); padding:26px 0 10px; color:var(--ink-3); font-size:11.5px; line-height:1.6;}
footer a{color:var(--ink-2);}

@media (max-width:700px){
  .case-row .c-region{display:none;}
}
</style>

<div class="hero">
  <div class="wrap">
    <div class="hero-top">
      <div class="eyebrow">New York &amp; New Jersey Capital Project Enforcement &amp; Litigation Risk</div>
      <div class="hero-actions">
        <a href="#" id="reset-link">Reset filters</a>
        <span id="db-status"></span>
      </div>
    </div>
    <h1>NYNJ Capital Risk Data</h1>
    <p>__N_CASES__ hand-verified New York and New Jersey capital-project enforcement cases, including the Port Authority of NY &amp; NJ. Filter by state, category, severity, or region below.</p>
    <div class="stat-strip" id="hero-stats"></div>
  </div>
</div>

<div class="wrap">

  <section>
    <div class="section-head"><h2>Where the cases are</h2><span class="hint">Sized by case count in the current filtered set &middot; click a region to filter, hover for detail</span></div>
    <div class="card map-card" id="map-host"></div>
  </section>

  <section>
    <div class="section-head"><h2>Filters</h2><span class="hint">Combine freely &mdash; the map, exhibits, and register below update live</span></div>
    <div class="card filters">
      <div class="search-row">
        <input type="search" id="f-search" placeholder="Search title, summary, entities, agency&hellip;">
      </div>
      <div class="chip-group" id="f-state"><span class="gl">State</span></div>
      <div class="chip-group" id="f-category"><span class="gl">Category</span></div>
      <div class="chip-group" id="f-severity"><span class="gl">Severity</span></div>
      <div class="chip-group" id="f-verification"><span class="gl">Verification</span></div>
      <div class="select-row">
        <label>Region <select id="f-region"></select></label>
        <label>Agency <select id="f-agency"></select></label>
        <label>Project type <select id="f-type"></select></label>
        <label>Review status <select id="f-review">
          <option value="">All</option>
          <option value="unreviewed">Unreviewed</option>
          <option value="flagged">Flagged</option>
          <option value="cleared">Cleared</option>
        </select></label>
        <label>Year from <input type="number" id="f-year-from" inputmode="numeric"></label>
        <label>Year to <input type="number" id="f-year-to" inputmode="numeric"></label>
      </div>
      <div class="filters-foot"><button class="btn-reset" id="btn-reset">Reset filters</button></div>
    </div>
  </section>

  <section>
    <div class="section-head"><h2>Exhibits &middot; filtered set</h2><span class="hint">Recomputed from whatever the filters above currently match</span></div>
    <div class="chart-grid">
      <div class="card chart-card"><h3>Exposure by control category</h3><div id="chart-category"></div></div>
      <div class="card chart-card"><h3>Exposure by state</h3><div id="chart-state"></div></div>
      <div class="card chart-card"><h3>Severity mix</h3><div id="chart-severity"></div></div>
      <div class="card chart-card"><h3>Cases by period, by verification</h3><div id="chart-timeline"></div></div>
      <div class="card chart-card" style="grid-column:1/-1;">
        <h3>Fraud-mechanism typology (precomputed classification)</h3>
        <div id="chart-ai-archetype"></div>
      </div>
    </div>
  </section>

  <section>
    <div class="toolbar">
      <div class="count" id="result-count"></div>
      <div class="sort-control">
        <label for="f-sort">Sort</label>
        <select id="f-sort">
          <option value="date-desc">Date, newest first</option>
          <option value="date-asc">Date, oldest first</option>
          <option value="amount-desc">Exposure, highest first</option>
          <option value="amount-asc">Exposure, lowest first</option>
          <option value="severity">Severity, most severe first</option>
          <option value="agency">Agency, A&ndash;Z</option>
        </select>
      </div>
    </div>
    <div class="table-wrap">
      <table class="case-table">
        <thead>
          <tr>
            <th class="c-date">Date</th>
            <th>State</th>
            <th>Agency / project</th>
            <th class="c-region">Region</th>
            <th>Category</th>
            <th>Severity</th>
            <th>Verif.</th>
            <th class="c-amount">Amount</th>
            <th>Rev.</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="case-list"></tbody>
      </table>
    </div>
    <div id="case-empty"></div>
  </section>
''' + RISK_SECTION_HTML + NARRATIVE_SECTION_HTML + '''

  <section id="ai-section">
    <div class="section-head"><h2>Typology methodology</h2><span class="hint">How the fraud-mechanism classification above was produced</span></div>
    <div class="card ai-panel">
      <p class="ai-intro">Each case is tagged with a fraud-mechanism archetype, its concrete red flags, and the verification step that would have closed the gap &mdash; adapted from recent transportation-fraud research methods. This is <b>precomputed once</b> from each case's already-cited source, not generated live. Treat it as a hypothesis for review, not a verified finding.</p>
    </div>
  </section>

  <footer>
    <p>Built from the same independently verified dataset as the companion memo and deck &mdash; see those for full sourcing and methodology. Typology and risk tiers are precomputed; nothing on this page runs a live model call.</p>
    <p>Theo Bae &middot; <span id="footer-date"></span></p>
  </footer>
</div>

<script id="case-data" type="application/json">'''

TAIL_AFTER_DATA = '''</script>
<script>
(function(){
  "use strict";

  var RAW = JSON.parse(document.getElementById('case-data').textContent);
  var CASES = RAW.cases;
  var META = RAW.meta;

  var CAT_ABBR = {
    "Procurement & Bid-Integrity Controls": "Procurement & bid integrity",
    "MWBE/DBE & Professional-Certification Controls": "MWBE/DBE & certification",
    "Payroll, Timekeeping & Certified-Payroll Controls": "Payroll & certified payroll",
    "Disbursement, Invoice & Change-Order Controls": "Disbursement & invoice",
    "Bribery, Kickback & Authorization Controls": "Bribery & authorization",
    "Conflict-of-Interest & Ethics Controls": "Conflict of interest",
    "Economic-Development & Tax-Incentive Controls": "Economic dev. & tax incentive"
  };
  var CATEGORY_ORDER = [
    "Procurement & Bid-Integrity Controls",
    "MWBE/DBE & Professional-Certification Controls",
    "Payroll, Timekeeping & Certified-Payroll Controls",
    "Disbursement, Invoice & Change-Order Controls",
    "Bribery, Kickback & Authorization Controls",
    "Conflict-of-Interest & Ethics Controls",
    "Economic-Development & Tax-Incentive Controls"
  ];
  var SEVERITY_ORDER = ["Material Weakness", "Significant Deficiency", "Control Deficiency"];
  var SEVERITY_CLASS = {"Material Weakness":"mw", "Significant Deficiency":"sd", "Control Deficiency":"cd"};
  var SEVERITY_SHORT = {"Material Weakness":"Mat. weak.", "Significant Deficiency":"Sig. def.", "Control Deficiency":"Ctrl. def."};
  var VERIFICATION_ORDER = ["confirmed", "probable", "uncorroborated"];
  var VERIFICATION_LABEL = {confirmed:"Confirmed", probable:"Probable", uncorroborated:"Uncorroborated"};
  var VERIFICATION_SHORT = {confirmed:"Conf.", probable:"Prob.", uncorroborated:"Uncorr."};
  var VERIFICATION_CLASS = {confirmed:"c", probable:"p", uncorroborated:"u"};
  var STATE_ORDER = ["NY", "NJ", "NY/NJ"];
  var STATE_LABEL = {"NY":"New York (NY)", "NJ":"New Jersey (NJ)", "NY/NJ":"Port Authority (NY/NJ)"};
  var STATE_LABEL_SHORT = {"NY":"New York", "NJ":"New Jersey", "NY/NJ":"Port Authority"};
  var STATE_CLASS = {"NY":"ny", "NJ":"nj", "NY/NJ":"bi"};
  var RISK_TIER_CLASS = {"Elevated Focus":"elevated", "Recurring Pattern":"recurring", "Isolated Precedent":"isolated"};

  var REGION_NODES = [
    {key:"Western NY", label:"Western NY", state:"NY", cx:55, cy:70},
    {key:"Capital Region", label:"Capital Region", state:"NY", cx:218, cy:52},
    {key:"Hudson Valley", label:"Hudson Valley", state:"NY", cx:192, cy:128},
    {key:"New York City", label:"New York City", state:"NY", cx:192, cy:198},
    {key:"Long Island", label:"Long Island", state:"NY", cx:283, cy:193},
    {key:"Northern NJ", label:"Northern NJ", state:"NJ", cx:138, cy:251},
    {key:"Central NJ", label:"Central NJ", state:"NJ", cx:128, cy:302},
    {key:"Southern NJ", label:"Southern NJ", state:"NJ", cx:112, cy:344}
  ];
  var REGION_CHIPS = [
    {key:"Statewide / Multi-Region", label:"Statewide (NY)"},
    {key:"Statewide / Multi-Region (NJ)", label:"Statewide (NJ)"}
  ];

  /* Fraud-mechanism archetypes: a taxonomy of HOW a scheme worked, distinct from the
     control_category taxonomy above (which describes WHICH control failed). Every case was
     classified once against this fixed list at dataset build time -- see data/ai_typology.json
     and the "Typology methodology" section below. */
  var AI_ARCHETYPES = [
    "Bid-Rigging / Collusive Procurement",
    "Pass-Through / Shell MWBE-DBE Vendor",
    "Bribery, Kickback or Undisclosed Payment",
    "Invoice or Change-Order Manipulation",
    "Certification or Identity Fraud",
    "Payroll / Certified-Payroll & Wage Theft",
    "Tax-Incentive or Economic-Development Abuse",
    "Conflict of Interest / Undisclosed Relationship"
  ];

  function cssVar(name){
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function money(x, decimals){
    x = Number(x) || 0;
    var neg = x < 0; x = Math.abs(x);
    var s;
    if (x >= 1e6) { var v = x/1e6; s = "$" + (Math.round(v*10)/10).toFixed(1) + "M"; }
    else if (x >= 1e3) { s = "$" + Math.round(x/1e3) + "K"; }
    else { s = "$" + Math.round(x); }
    return (neg ? "-" : "") + s;
  }
  function esc(s){
    return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  }
  function periodLabel(year){
    var start = 4 * Math.floor(year / 4);
    return start + "–" + (start + 3);
  }
  function caseAmount(c){ return c.counted ? (c.amount || 0) : 0; }

  var YEAR_MIN = CASES.reduce(function(m,c){ return Math.min(m,c.year); }, 9999);
  var YEAR_MAX = CASES.reduce(function(m,c){ return Math.max(m,c.year); }, 0);

  /* ---------------- review tracking state ---------------- */
  var review = {}; // caseId -> {status, note, updated_at}
  var dbNS = null;
  var writeFailed = false;

  function getReview(caseId){
    return review[caseId] || {status:"unreviewed", note:"", updated_at:null};
  }

  function setDbStatusText(text){
    var el = document.getElementById('db-status');
    if (el) el.textContent = text;
  }

  function initDb(){
    if (!window.claude || typeof window.claude.use !== "function"){
      setDbStatusText("View-only preview");
      return;
    }
    window.claude.use('db').then(function(ns){
      dbNS = ns;
      if (!dbNS){ setDbStatusText("View-only preview"); return; }
      setDbStatusText("Review status syncs live");
      try {
        dbNS.collection('review').onSnapshot(function(snap){
          snap.docs.forEach(function(d){
            if (d.exists) review[d.id] = d.data();
          });
          renderAll();
        }, function(err){
          console.error('review subscribe error', err);
        });
      } catch(e){ console.error(e); }
    }).catch(function(e){ console.error(e); setDbStatusText("View-only preview"); });
  }

  function saveReview(caseId, patch){
    var current = getReview(caseId);
    var next = {
      status: patch.status != null ? patch.status : current.status,
      note: patch.note != null ? patch.note : current.note,
      updated_at: new Date().toISOString()
    };
    review[caseId] = next;
    renderAll();
    if (!dbNS) return;
    dbNS.collection('review').doc(caseId).set(next).catch(function(e){
      console.error('save failed', e);
      writeFailed = true;
      renderAll();
    });
  }

  /* ---------------- precomputed typology + risk-tier rendering (static, no live calls) ---------------- */
  function riskContextHtml(c){
    var cls = RISK_TIER_CLASS[c.risk_tier] || 'isolated';
    var label = '<span class="risk-tier ' + cls + '">' + esc(c.risk_tier) + '</span>';
    var body;
    if (c.risk_pair_count <= 1){
      body = 'the only case in the register for this ' + esc(c.agency) + ' &times; ' + esc(CAT_ABBR[c.category]||c.category) + ' pairing.';
    } else {
      var win = String(c.risk_recent_window||'').split('-');
      body = 'this ' + esc(c.agency) + ' &times; ' + esc(CAT_ABBR[c.category]||c.category) + ' pairing has ' + c.risk_pair_count +
        ' cases in the register, ' + Math.round((c.risk_recency||0)*100) + '% of them from ' + (win[0]||'') + '–' + (win[1]||'') + '.';
    }
    return '<div class="case-risk-context">' + label + ' &mdash; ' + body + '</div>';
  }

  function renderAiCaseBlock(c){
    var head = '<div class="rb-head"><span class="rb-title">Typology &amp; verification gap</span></div>';
    return '<div class="ai-block">' + head +
      '<span class="tag tag-ai">' + esc(c.archetype) + '</span>' +
      (c.red_flags && c.red_flags.length ? '<ul class="ai-flags">' + c.red_flags.map(function(f){ return '<li>' + esc(f) + '</li>'; }).join('') + '</ul>' : '') +
      (c.verification_gap ? '<p class="ai-gap"><b>Verification gap</b>' + esc(c.verification_gap) + '</p>' : '') +
      '<div class="ai-case-meta">Confidence: ' + esc(c.confidence) + ' &middot; classified once from the case narrative already cited above, at dataset build time</div>' +
      riskContextHtml(c) +
      '<div class="ai-disclaimer">A structured read of the government\\u2019s own case narrative, done once at build time against a fixed taxonomy &mdash; a hypothesis for review, not a verified finding.</div>' +
      '</div>';
  }

  function drawAiArchetypeChart(list){
    var host = document.getElementById('chart-ai-archetype');
    if (!list.length){ host.innerHTML = '<div class="chart-empty">No matching cases</div>'; return; }
    var counts = {};
    AI_ARCHETYPES.forEach(function(a){ counts[a] = 0; });
    list.forEach(function(c){ counts[c.archetype] = (counts[c.archetype]||0) + 1; });
    var order = AI_ARCHETYPES.filter(function(a){ return counts[a] > 0; });
    var max = Math.max.apply(null, order.map(function(a){ return counts[a]; })) || 1;
    var rowH = 24, gap = 7, top = 4;
    var w = 620, labelW = 260, rightW = 40, barMaxW = w - labelW - rightW;
    var h = top*2 + order.length*(rowH+gap) - gap;
    var svg = '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="Precomputed fraud-mechanism typology among the current filtered cases">';
    order.forEach(function(a, i){
      var y = top + i*(rowH+gap);
      var wpx = Math.max(2, (counts[a]/max) * barMaxW);
      svg += '<text x="0" y="' + (y+rowH/2+4) + '" font-size="10" font-family="var(--font-body)" fill="var(--ink-2)">' + esc(a) + '</text>';
      svg += '<rect x="' + labelW + '" y="' + y + '" width="' + wpx + '" height="' + rowH + '" rx="1" fill="var(--ai)"></rect>';
      svg += '<text x="' + (labelW + wpx + 8) + '" y="' + (y+rowH/2+4) + '" font-size="10" font-family="var(--font-mono)" fill="var(--ink)">' + counts[a] + '</text>';
    });
    svg += '</svg>';
    host.innerHTML = svg;
  }

  /* ---------------- filter state ---------------- */
  var openCards = {};
  var state = {
    search: "",
    state: {},
    category: {},
    severity: {},
    verification: {},
    region: "",
    agency: "",
    type: "",
    review: "",
    yearFrom: YEAR_MIN,
    yearTo: YEAR_MAX,
    sort: "date-desc"
  };

  function anySelected(map){ return Object.keys(map).some(function(k){ return map[k]; }); }

  function matches(c){
    if (state.search){
      var q = state.search.toLowerCase();
      var hay = [c.title, c.summary, c.entities, c.agency, c.violation].join(" ").toLowerCase();
      if (hay.indexOf(q) === -1) return false;
    }
    if (anySelected(state.state) && !state.state[c.state]) return false;
    if (anySelected(state.category) && !state.category[c.category]) return false;
    if (anySelected(state.severity) && !state.severity[c.severity]) return false;
    if (anySelected(state.verification) && !state.verification[c.verification]) return false;
    if (state.region && c.region !== state.region) return false;
    if (state.agency && c.agency !== state.agency) return false;
    if (state.type && c.type !== state.type) return false;
    if (state.review){
      var rs = getReview(c.id).status;
      if (rs !== state.review) return false;
    }
    if (c.year < state.yearFrom || c.year > state.yearTo) return false;
    return true;
  }

  function sortCases(list){
    var sev = state.sort;
    var out = list.slice();
    var sevRank = {"Material Weakness":0, "Significant Deficiency":1, "Control Deficiency":2};
    out.sort(function(a,b){
      switch(sev){
        case "date-asc": return a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
        case "amount-desc": return caseAmount(b) - caseAmount(a);
        case "amount-asc": return caseAmount(a) - caseAmount(b);
        case "severity": return sevRank[a.severity] - sevRank[b.severity] || (a.date < b.date ? 1 : -1);
        case "agency": return a.agency.localeCompare(b.agency) || (a.date < b.date ? 1 : -1);
        case "date-desc":
        default: return a.date < b.date ? 1 : a.date > b.date ? -1 : 0;
      }
    });
    return out;
  }

  /* ---------------- chart drawing (recomputed from the filtered set) ---------------- */
  function drawCategoryChart(list){
    var host = document.getElementById('chart-category');
    if (!list.length){ host.innerHTML = '<div class="chart-empty">No matching cases</div>'; return; }
    var totals = {}; var counts = {};
    CATEGORY_ORDER.forEach(function(cat){ totals[cat]=0; counts[cat]=0; });
    list.forEach(function(c){ totals[c.category]+=caseAmount(c); counts[c.category]+=1; });
    var max = Math.max.apply(null, CATEGORY_ORDER.map(function(k){return totals[k];})) || 1;
    var rowH = 26, gap = 7, top = 4;
    var w = 460, labelW = 148, rightW = 92, barMaxW = w - labelW - rightW;
    var h = top*2 + CATEGORY_ORDER.length*(rowH+gap) - gap;
    var svg = '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="Exposure by control category">';
    CATEGORY_ORDER.forEach(function(cat, i){
      var y = top + i*(rowH+gap);
      var wpx = Math.max(2, (totals[cat]/max) * barMaxW);
      svg += '<text x="0" y="' + (y+rowH/2+4) + '" font-size="10" font-family="var(--font-body)" fill="var(--ink-2)">' + esc(CAT_ABBR[cat]) + '</text>';
      svg += '<rect x="' + labelW + '" y="' + y + '" width="' + wpx + '" height="' + rowH + '" rx="1" fill="var(--blue)"></rect>';
      svg += '<text x="' + (labelW + wpx + 8) + '" y="' + (y+rowH/2+4) + '" font-size="10" font-family="var(--font-mono)" fill="var(--ink)">' + money(totals[cat]) + ' (' + counts[cat] + ')</text>';
    });
    svg += '</svg>';
    host.innerHTML = svg;
  }

  function drawStateChart(list){
    var host = document.getElementById('chart-state');
    if (!list.length){ host.innerHTML = '<div class="chart-empty">No matching cases</div>'; return; }
    var totals = {}; var counts = {};
    STATE_ORDER.forEach(function(s){ totals[s]=0; counts[s]=0; });
    list.forEach(function(c){ totals[c.state]=(totals[c.state]||0)+caseAmount(c); counts[c.state]=(counts[c.state]||0)+1; });
    var max = Math.max.apply(null, STATE_ORDER.map(function(k){return totals[k]||0;})) || 1;
    var colorVar = {"NY":"var(--blue)", "NJ":"var(--orange)", "NY/NJ":"var(--aqua)"};
    var rowH = 26, gap = 7, top = 4;
    var w = 460, labelW = 108, rightW = 92, barMaxW = w - labelW - rightW;
    var h = top*2 + STATE_ORDER.length*(rowH+gap) - gap;
    var svg = '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="Exposure by state">';
    STATE_ORDER.forEach(function(s, i){
      var y = top + i*(rowH+gap);
      var t = totals[s] || 0, n = counts[s] || 0;
      var wpx = Math.max(2, (t/max) * barMaxW);
      svg += '<text x="0" y="' + (y+rowH/2+4) + '" font-size="10" font-family="var(--font-body)" fill="var(--ink-2)">' + esc(STATE_LABEL_SHORT[s]) + '</text>';
      svg += '<rect x="' + labelW + '" y="' + y + '" width="' + wpx + '" height="' + rowH + '" rx="1" fill="' + colorVar[s] + '"></rect>';
      svg += '<text x="' + (labelW + wpx + 8) + '" y="' + (y+rowH/2+4) + '" font-size="10" font-family="var(--font-mono)" fill="var(--ink)">' + money(t) + ' (' + n + ')</text>';
    });
    svg += '</svg>';
    host.innerHTML = svg;
  }

  function drawSeverityChart(list){
    var host = document.getElementById('chart-severity');
    if (!list.length){ host.innerHTML = '<div class="chart-empty">No matching cases</div>'; return; }
    var counts = {"Material Weakness":0, "Significant Deficiency":0, "Control Deficiency":0};
    list.forEach(function(c){ counts[c.severity] = (counts[c.severity]||0) + 1; });
    var total = list.length;
    var colorVar = {"Material Weakness":"var(--serious)", "Significant Deficiency":"var(--warning)", "Control Deficiency":"var(--good)"};
    var w = 420, barY = 10, barH = 30;
    var legendRowH = 20, legendTop = barY + barH + 18;
    var h = legendTop + SEVERITY_ORDER.length * legendRowH + 2;
    var svg = '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="Severity mix">';
    var x = 0;
    SEVERITY_ORDER.forEach(function(sev){
      var pct = counts[sev] / total;
      var segW = pct * w;
      if (segW > 0.5){
        svg += '<rect x="' + x + '" y="' + barY + '" width="' + Math.max(0,segW-1) + '" height="' + barH + '" fill="' + colorVar[sev] + '"></rect>';
        if (segW > 40){
          svg += '<text x="' + (x+segW/2) + '" y="' + (barY+barH/2+4) + '" font-size="10.5" font-family="var(--font-mono)" font-weight="600" fill="#fff" text-anchor="middle">' + Math.round(pct*100) + '%</text>';
        }
      }
      x += segW;
    });
    SEVERITY_ORDER.forEach(function(sev, i){
      var ly = legendTop + i*legendRowH;
      svg += '<rect x="0" y="' + (ly-9) + '" width="9" height="9" fill="' + colorVar[sev] + '"></rect>';
      var pct = total ? Math.round((counts[sev]/total)*100) : 0;
      svg += '<text x="15" y="' + ly + '" font-size="10.5" font-family="var(--font-body)" fill="var(--ink-2)">' + esc(sev) + ' — ' + counts[sev] + ' (' + pct + '%)</text>';
    });
    svg += '</svg>';
    host.innerHTML = svg;
  }

  function drawTimelineChart(list){
    var host = document.getElementById('chart-timeline');
    if (!list.length){ host.innerHTML = '<div class="chart-empty">No matching cases</div>'; return; }
    var periods = [];
    for (var y = 4*Math.floor(YEAR_MIN/4); y <= YEAR_MAX; y += 4){ periods.push(periodLabel(y)); }
    var bins = {};
    periods.forEach(function(p){ bins[p] = {confirmed:0, probable:0, uncorroborated:0}; });
    list.forEach(function(c){
      var p = periodLabel(c.year);
      if (!bins[p]) bins[p] = {confirmed:0, probable:0, uncorroborated:0};
      bins[p][c.verification] = (bins[p][c.verification]||0) + 1;
    });
    periods = Object.keys(bins).sort();
    var max = 1;
    periods.forEach(function(p){ var t = bins[p].confirmed+bins[p].probable+bins[p].uncorroborated; if (t>max) max=t; });
    var w = 420, h = 150, padB = 30, padT = 8, colW = w/periods.length, barW = Math.min(46, colW*0.55);
    var colorVar = {confirmed:"var(--good)", probable:"var(--warning)", uncorroborated:"var(--serious)"};
    var svg = '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="Cases by period">';
    periods.forEach(function(p, i){
      var cx = i*colW + colW/2;
      var y = h - padB;
      VERIFICATION_ORDER.forEach(function(v){
        var n = bins[p][v] || 0;
        if (!n) return;
        var segH = (n/max) * (h-padB-padT);
        svg += '<rect x="' + (cx-barW/2) + '" y="' + (y-segH) + '" width="' + barW + '" height="' + Math.max(0,segH-1) + '" fill="' + colorVar[v] + '"></rect>';
        y -= segH;
      });
      svg += '<text x="' + cx + '" y="' + (h-8) + '" font-size="9.5" fill="var(--ink-3)" text-anchor="middle" font-family="var(--font-mono)">' + p + '</text>';
    });
    svg += '</svg>';
    host.innerHTML = svg;
  }

  /* ---------------- map (recomputed from the filtered set) ---------------- */
  function drawMap(list){
    var host = document.getElementById('map-host');
    var agg = {};
    REGION_NODES.concat(REGION_CHIPS).forEach(function(r){ agg[r.key] = {count:0, exposure:0, bi:0}; });
    list.forEach(function(c){
      if (!agg[c.region]) agg[c.region] = {count:0, exposure:0, bi:0};
      agg[c.region].count += 1;
      agg[c.region].exposure += caseAmount(c);
      if (c.state === "NY/NJ") agg[c.region].bi += 1;
    });

    var svg = '<svg viewBox="0 0 320 402" role="img" aria-label="Map of case regions across New York and New Jersey">';
    svg += '<polygon class="map-bg-ny" points="18,18 45,8 120,5 190,10 250,35 258,85 232,140 214,180 196,214 150,207 95,175 55,130 30,75"></polygon>';
    svg += '<polygon class="map-bg-li" points="212,194 252,180 304,193 312,204 258,216 212,216"></polygon>';
    svg += '<polygon class="map-bg-nj" points="150,207 196,214 188,258 172,298 150,344 122,376 94,356 90,306 102,256 124,222"></polygon>';
    svg += '<text class="map-region-label" x="58" y="26">NEW YORK</text>';
    svg += '<text class="map-region-label" x="122" y="393">NEW JERSEY</text>';

    REGION_NODES.forEach(function(r){
      var a = agg[r.key];
      var radius = a.count ? Math.max(9, Math.min(22, 8 + Math.sqrt(a.count) * 4)) : 6;
      var colorVar = r.state === "NY" ? "var(--blue)" : "var(--orange)";
      var selected = state.region === r.key;
      var fillOpacity = a.count ? 1 : 0.22;
      var tip = esc(r.label) + ' — ' + a.count + (a.count === 1 ? ' case, ' : ' cases, ') + money(a.exposure) + (a.bi ? ' (' + a.bi + ' bi-state)' : '') + '. Click to filter.';
      svg += '<g class="map-node' + (selected ? ' selected' : '') + '" data-region="' + esc(r.key) + '">';
      svg += '<circle cx="' + r.cx + '" cy="' + r.cy + '" r="' + radius + '" fill="' + colorVar + '" fill-opacity="' + fillOpacity + '"' + (a.bi ? ' stroke="var(--aqua)" stroke-width="2.5"' : '') + '>';
      svg += '<title>' + tip + '</title>';
      svg += '</circle>';
      if (a.count) svg += '<text class="node-count" x="' + r.cx + '" y="' + (r.cy + 3.5) + '" font-size="' + (radius > 13 ? 11 : 9.5) + '">' + a.count + '</text>';
      svg += '<text class="node-label" x="' + r.cx + '" y="' + (r.cy + radius + 11) + '" font-size="8.5">' + esc(r.label) + '</text>';
      svg += '</g>';
    });
    svg += '</svg>';

    var chipsHtml = '<div class="map-chips">' + REGION_CHIPS.map(function(r){
      var a = agg[r.key];
      var pressed = state.region === r.key;
      return '<button type="button" class="map-chip" data-region="' + esc(r.key) + '" aria-pressed="' + pressed + '">' + esc(r.label) + ' · ' + a.count + '</button>';
    }).join('') + '</div>';

    host.innerHTML =
      '<div class="map-wrap">' +
        '<div class="map-svg-wrap">' + svg + '</div>' +
        '<div class="map-side">' +
          '<div class="map-legend">' +
            '<span class="map-legend-item"><i style="background:var(--blue); border-color:var(--blue);"></i>New York region</span>' +
            '<span class="map-legend-item"><i style="background:var(--orange); border-color:var(--orange);"></i>New Jersey region</span>' +
            '<span class="map-legend-item"><i class="ring"></i>Includes Port Authority (bi-state) cases</span>' +
          '</div>' +
          chipsHtml +
          '<p class="map-hint">Circle size tracks case count in the current filters. Two statewide/multi-region groupings aren’t tied to one area — use the chips above, or the region filter below.</p>' +
        '</div>' +
      '</div>';

    host.querySelectorAll('[data-region]').forEach(function(el){
      el.addEventListener('click', function(){
        var region = el.getAttribute('data-region');
        state.region = (state.region === region) ? "" : region;
        var sel = document.getElementById('f-region');
        if (sel) sel.value = state.region;
        renderAll();
      });
    });
  }

  /* ---------------- filter chip / select population ---------------- */
  function buildChipGroup(hostId, key, values, classFn){
    var host = document.getElementById(hostId);
    values.forEach(function(v){
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip' + (classFn ? (' ' + classFn(v.value)) : '');
      btn.textContent = v.label;
      btn.setAttribute('aria-pressed', 'false');
      btn.addEventListener('click', function(){
        state[key][v.value] = !state[key][v.value];
        btn.setAttribute('aria-pressed', state[key][v.value] ? 'true' : 'false');
        renderAll();
      });
      host.appendChild(btn);
    });
  }

  function buildSelect(id, values, placeholder){
    var sel = document.getElementById(id);
    var opt = document.createElement('option');
    opt.value = ''; opt.textContent = placeholder;
    sel.appendChild(opt);
    values.forEach(function(v){
      var o = document.createElement('option');
      o.value = v; o.textContent = v;
      sel.appendChild(o);
    });
  }

  function uniqueSorted(field){
    var set = {};
    CASES.forEach(function(c){ set[c[field]] = true; });
    return Object.keys(set).sort();
  }

  /* ---------------- case register (table) rendering ---------------- */
  function sevTagClass(sev){ return "tag tag-" + (SEVERITY_CLASS[sev] || "mw"); }
  function verTagClass(v){ return "tag tag-ver-" + (VERIFICATION_CLASS[v] || "u"); }
  function stateTagClass(v){ return "tag tag-st-" + (STATE_CLASS[v] || "ny"); }

  function caseRowHtml(c){
    var r = getReview(c.id);
    var open = !!openCards[c.id];
    var readonlyMsg = writeFailed ? '<div class="readonly-note show">Changes here are shown only in your current view &mdash; this link is read-only, so nothing was saved centrally.</div>' : '';
    var row = '' +
      '<tr class="case-row" data-open="' + open + '" data-toggle="' + esc(c.id) + '" id="case-' + esc(c.id) + '">' +
        '<td class="c-date">' + esc(c.date) + '</td>' +
        '<td><span class="' + stateTagClass(c.state) + '">' + esc(c.state) + '</span></td>' +
        '<td class="c-agency">' + esc(c.agency) + '<small>' + esc(c.type) + '</small></td>' +
        '<td class="c-region">' + esc(c.region) + '</td>' +
        '<td><span class="tag tag-cat">' + esc(CAT_ABBR[c.category] || c.category) + '</span></td>' +
        '<td><span class="' + sevTagClass(c.severity) + '" title="' + esc(c.severity) + '">' + esc(SEVERITY_SHORT[c.severity] || c.severity) + '</span></td>' +
        '<td><span class="' + verTagClass(c.verification) + '">' + esc(VERIFICATION_SHORT[c.verification]) + '</span></td>' +
        '<td class="c-amount tnum">' + (c.counted ? money(c.amount) : 'N/A') + '</td>' +
        '<td class="c-rev"><span class="review-dot ' + esc(r.status) + '" title="Review: ' + esc(r.status) + '"></span></td>' +
        '<td class="c-chev">&#9656;</td>' +
      '</tr>';
    var detail = '' +
      '<tr class="case-detail-row"><td colspan="10"><div class="case-detail">' +
        '<h4>' + esc(c.title) + '</h4>' +
        '<p>' + esc(c.summary) + '</p>' +
        '<dl class="meta-grid">' +
          '<div><dt>State</dt><dd>' + esc(STATE_LABEL[c.state] || c.state) + '</dd></div>' +
          '<div><dt>Entities</dt><dd>' + esc(c.entities) + '</dd></div>' +
          '<div><dt>Violation type</dt><dd>' + esc(c.violation) + '</dd></div>' +
          '<div><dt>Magnitude / pervasiveness</dt><dd>' + esc(c.magnitude) + ' &middot; ' + esc(c.pervasiveness) + '</dd></div>' +
          '<div><dt>Dollar basis</dt><dd>' + esc(c.basis || '—') + (c.counted ? '' : ' (excluded from aggregate total)') + '</dd></div>' +
          '<div><dt>Stage</dt><dd>' + esc(c.stage) + '</dd></div>' +
          '<div><dt>Scheme family</dt><dd class="mono">' + esc(c.scheme) + '</dd></div>' +
        '</dl>' +
        '<div class="source-line">Source: ' + esc(c.source) + (c.url ? ' &middot; <a href="' + esc(c.url) + '" target="_blank" rel="noopener">view release</a>' : '') + (c.corroboration ? '<br>Corroboration: ' + esc(c.corroboration) : '') + '</div>' +
        '<div class="review-box">' +
          '<div class="rb-head">' +
            '<span class="rb-title">Diligence review</span>' +
            '<div class="status-btns">' +
              statusBtn(c.id, 'unreviewed', 'Unreviewed', r.status) +
              statusBtn(c.id, 'flagged', 'Flag for follow-up', r.status) +
              statusBtn(c.id, 'cleared', 'Cleared', r.status) +
            '</div>' +
          '</div>' +
          '<textarea data-note="' + esc(c.id) + '" placeholder="Notes for follow-up&hellip;">' + esc(r.note) + '</textarea>' +
          '<div class="review-meta">' + (r.updated_at ? ('Last updated ' + new Date(r.updated_at).toLocaleString()) : 'Not yet reviewed') + '</div>' +
          readonlyMsg +
        '</div>' +
        renderAiCaseBlock(c) +
      '</div></td></tr>';
    return row + detail;
  }

  function statusBtn(caseId, value, label, current){
    var cls = value === 'flagged' ? 's-flagged' : value === 'cleared' ? 's-cleared' : 's-unreviewed';
    return '<button type="button" class="status-btn ' + cls + '" data-status="' + value + '" data-case="' + esc(caseId) + '" aria-pressed="' + (current === value) + '">' + label + '</button>';
  }

  /* ---------------- main render ---------------- */
  function renderHeroStats(){
    var host = document.getElementById('hero-stats');
    var mw = META.severity_summary.by_severity[0];
    var byState = META.by_state || [];
    var stateBits = byState.map(function(s){ return s.state + ' ' + s.case_count; }).join(' · ');
    var tiles = [
      [String(META.n_cases), 'verified unique cases'],
      [stateBits, 'by state'],
      [money(META.total_exposure), 'exposure implicated'],
      [META.confirmed_pct + '%', 'independently confirmed'],
      [mw.case_pct + '%', 'material weakness by case count']
    ];
    host.innerHTML = tiles.map(function(t){
      var style = String(t[0]).length > 10 ? ' style="font-size:14px"' : '';
      return '<div class="stat-cell"><div class="n tnum"' + style + '>' + esc(t[0]) + '</div><div class="l">' + esc(t[1]) + '</div></div>';
    }).join('');
  }

  function renderAll(){
    var filtered = CASES.filter(matches);
    var sorted = sortCases(filtered);

    drawMap(filtered);
    drawCategoryChart(filtered);
    drawStateChart(filtered);
    drawSeverityChart(filtered);
    drawTimelineChart(filtered);
    drawAiArchetypeChart(filtered);

    var totalExposure = filtered.reduce(function(s,c){ return s + caseAmount(c); }, 0);
    document.getElementById('result-count').innerHTML =
      'Showing <b>' + filtered.length + '</b> of ' + CASES.length + ' cases &middot; <b>' + money(totalExposure) + '</b> exposure';

    var listHost = document.getElementById('case-list');
    var emptyHost = document.getElementById('case-empty');
    if (!sorted.length){
      listHost.innerHTML = '';
      emptyHost.innerHTML = '<div class="card empty-state">No cases match these filters.<br><button class="btn-reset" id="btn-empty-reset">Reset filters</button></div>';
      var er = document.getElementById('btn-empty-reset');
      if (er) er.addEventListener('click', resetFilters);
    } else {
      emptyHost.innerHTML = '';
      listHost.innerHTML = sorted.map(caseRowHtml).join('');
    }

    // wire up interactions on the freshly rendered rows
    listHost.querySelectorAll('[data-toggle]').forEach(function(el){
      el.addEventListener('click', function(){
        var id = el.getAttribute('data-toggle');
        openCards[id] = !openCards[id];
        renderAll();
      });
    });
    listHost.querySelectorAll('.status-btn').forEach(function(btn){
      btn.addEventListener('click', function(e){
        e.stopPropagation();
        saveReview(btn.getAttribute('data-case'), {status: btn.getAttribute('data-status')});
      });
    });
    listHost.querySelectorAll('textarea[data-note]').forEach(function(ta){
      ta.addEventListener('click', function(e){ e.stopPropagation(); });
      ta.addEventListener('blur', function(){
        saveReview(ta.getAttribute('data-note'), {note: ta.value});
      });
    });
  }

  function resetFilters(){
    state.search = "";
    state.state = {}; state.category = {}; state.severity = {}; state.verification = {};
    state.region = ""; state.agency = ""; state.type = ""; state.review = "";
    state.yearFrom = YEAR_MIN; state.yearTo = YEAR_MAX;
    document.getElementById('f-search').value = "";
    document.querySelectorAll('.chip').forEach(function(c){ c.setAttribute('aria-pressed','false'); });
    document.getElementById('f-region').value = "";
    document.getElementById('f-agency').value = "";
    document.getElementById('f-type').value = "";
    document.getElementById('f-review').value = "";
    document.getElementById('f-year-from').value = YEAR_MIN;
    document.getElementById('f-year-to').value = YEAR_MAX;
    renderAll();
  }

  function wireFilterInputs(){
    document.getElementById('f-search').addEventListener('input', function(e){
      state.search = e.target.value; renderAll();
    });
    document.getElementById('f-region').addEventListener('change', function(e){ state.region = e.target.value; renderAll(); });
    document.getElementById('f-agency').addEventListener('change', function(e){ state.agency = e.target.value; renderAll(); });
    document.getElementById('f-type').addEventListener('change', function(e){ state.type = e.target.value; renderAll(); });
    document.getElementById('f-review').addEventListener('change', function(e){ state.review = e.target.value; renderAll(); });
    document.getElementById('f-year-from').addEventListener('change', function(e){
      state.yearFrom = parseInt(e.target.value, 10) || YEAR_MIN; renderAll();
    });
    document.getElementById('f-year-to').addEventListener('change', function(e){
      state.yearTo = parseInt(e.target.value, 10) || YEAR_MAX; renderAll();
    });
    document.getElementById('f-sort').addEventListener('change', function(e){ state.sort = e.target.value; renderAll(); });
    document.getElementById('btn-reset').addEventListener('click', resetFilters);
    document.getElementById('reset-link').addEventListener('click', function(e){ e.preventDefault(); resetFilters(); });
  }

  function init(){
    renderHeroStats();

    buildChipGroup('f-state', 'state', STATE_ORDER.map(function(s){ return {value:s, label:STATE_LABEL[s]}; }), function(v){ return 'st-' + STATE_CLASS[v]; });
    buildChipGroup('f-category', 'category', CATEGORY_ORDER.map(function(c){ return {value:c, label:CAT_ABBR[c]}; }));
    buildChipGroup('f-severity', 'severity', SEVERITY_ORDER.map(function(s){ return {value:s, label:s}; }), function(v){ return 'sev-' + SEVERITY_CLASS[v]; });
    buildChipGroup('f-verification', 'verification', VERIFICATION_ORDER.map(function(v){ return {value:v, label:VERIFICATION_LABEL[v]}; }), function(v){ return 'ver-' + VERIFICATION_CLASS[v]; });

    buildSelect('f-region', uniqueSorted('region'), 'All regions');
    buildSelect('f-agency', uniqueSorted('agency'), 'All agencies');
    buildSelect('f-type', uniqueSorted('type'), 'All project types');

    document.getElementById('f-year-from').value = YEAR_MIN;
    document.getElementById('f-year-to').value = YEAR_MAX;
    document.getElementById('f-year-from').min = YEAR_MIN; document.getElementById('f-year-from').max = YEAR_MAX;
    document.getElementById('f-year-to').min = YEAR_MIN; document.getElementById('f-year-to').max = YEAR_MAX;

    wireFilterInputs();

    // deep link: #case-<id>
    if (location.hash && location.hash.indexOf('#case-') === 0){
      var id = location.hash.slice(6);
      openCards[id] = true;
    }

    renderAll();

    if (location.hash && location.hash.indexOf('#case-') === 0){
      var target = document.getElementById(location.hash.slice(1));
      if (target) target.scrollIntoView({behavior:'smooth', block:'start'});
    }

    document.getElementById('footer-date').textContent = new Date().toLocaleDateString(undefined, {year:'numeric', month:'long'});

    initDb();
  }

  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>

</body></html>'''

HEAD = HEAD.replace("__N_CASES__", str(len(CASES)))
full = HEAD + CASE_DATA_JSON + TAIL_AFTER_DATA

out_path = "capital_risk_tracker.html"
with open(out_path, "w") as f:
    f.write(full)

print("wrote", out_path, len(full), "bytes,", len(CASES), "cases")
print("risk tiers: elevated=%d recurring=%d isolated=%d" % (N_ELEVATED, N_RECURRING, N_ISOLATED))
