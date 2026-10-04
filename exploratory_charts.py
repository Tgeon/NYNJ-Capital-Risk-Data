"""
exploratory_charts.py -- four extra charts exploring the dataset beyond
the main analysis pipeline. Not wired into build_tracker.py -- a
standalone set of exhibits:

  1. Case volume and verification-tier mix by period -- shows that most
     of the dataset's volume is from 2004 onward and has been
     accelerating.
  2. Cumulative dollar exposure over time -- a growth-trajectory view of
     the same data, complementing the two-period waterfall in
     variance_analysis.py.
  3. Risk-tier matrix (bubble chart) -- visualizes data/risk_index.json's
     pervasiveness-by-recency rubric directly, which otherwise only
     appears as a table.
  4. Repeat-entity table -- a name-matching scan of the `entities` field
     that surfaces individuals or companies named in more than one case.
     Cross-checked against `scheme_family` and `count_in_dollar_total`:
     most of these were already correctly linked and deduplicated, which
     is itself a useful check on the dataset's dedup logic.

Palette, fonts, and style helpers match charts.py exactly, for visual
consistency with the project's other charts.
"""

import json
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as mticker

# ---- fonts (identical to charts.py) ------------------------------------
fm.fontManager.addfont("fonts/WorkSans-Regular.ttf")
fm.fontManager.addfont("fonts/WorkSans-Bold.ttf")
fm.fontManager.addfont("fonts/IBMPlexMono-Regular.ttf")
SANS = fm.FontProperties(fname="fonts/WorkSans-Regular.ttf").get_name()
SANS_BOLD = fm.FontProperties(fname="fonts/WorkSans-Bold.ttf").get_name()
MONO = fm.FontProperties(fname="fonts/IBMPlexMono-Regular.ttf").get_name()
plt.rcParams["font.family"] = SANS
BOLD = fm.FontProperties(fname="fonts/WorkSans-Bold.ttf")

# ---- palette (identical to charts.py) ----------------------------------
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

import os
os.makedirs("charts/exploratory", exist_ok=True)


def _style_ax(ax):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9.5)


def _titles(ax, title, subtitle, title_y=1.22, subtitle_y=1.06):
    ax.text(0, title_y, title, transform=ax.transAxes, fontsize=12.5,
             fontproperties=BOLD, color=INK, ha="left", va="bottom")
    ax.text(0, subtitle_y, subtitle, transform=ax.transAxes, fontsize=9,
             color=INK_SECONDARY, ha="left", va="bottom")


def fmt_dollar(x):
    if x >= 1_000_000:
        v = x / 1_000_000
        return f"${v:.0f}M" if v == int(v) else f"${v:.1f}M"
    if x >= 1_000:
        return f"${x/1_000:.0f}K"
    return f"${x:.0f}"


cases = json.load(open("data/cases_with_controls.json"))
cases = [c for c in cases if not c.get("is_duplicate")]


def counted_amount(c):
    return c["dollar_amount"] if c["count_in_dollar_total"] else 0


def period_label(year):
    """Same 4-year binning as variance_analysis.py, reused for consistency."""
    start = 4 * (year // 4)
    return f"{start}–{start + 3}"


for c in cases:
    c["period"] = period_label(c["year"])

periods = sorted(set(c["period"] for c in cases))

# =========================================================================
# Exhibit E1 -- case volume & verification-tier mix by period
# =========================================================================
def chart_volume_by_period():
    rows = []
    for p in periods:
        pc = [c for c in cases if c["period"] == p]
        conf = sum(1 for c in pc if c["verification_class"] == "confirmed")
        prob = sum(1 for c in pc if c["verification_class"] == "probable")
        unc = sum(1 for c in pc if c["verification_class"] == "uncorroborated")
        rows.append((p, conf, prob, unc))

    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    x = range(len(rows))
    conf_v = [r[1] for r in rows]
    prob_v = [r[2] for r in rows]
    unc_v = [r[3] for r in rows]

    ax.bar(x, conf_v, color=BLUE, width=0.62, label="Confirmed")
    ax.bar(x, prob_v, bottom=conf_v, color=WARNING, width=0.62, label="Probable")
    bottom2 = [a + b for a, b in zip(conf_v, prob_v)]
    ax.bar(x, unc_v, bottom=bottom2, color=INK_MUTED, width=0.62, label="Uncorroborated")

    totals = [r[1] + r[2] + r[3] for r in rows]
    for i, t in enumerate(totals):
        ax.text(i, t + 0.6, str(t), ha="center", va="bottom", fontsize=9.5,
                 fontproperties=SANS_BOLD, color=INK)

    ax.set_xticks(list(x))
    ax.set_xticklabels([r[0] for r in rows], fontsize=9)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True, nbins=6))
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    _style_ax(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncols=3,
              bbox_to_anchor=(0, 1.14))
    _titles(ax, "Case volume is concentrated in the last two decades",
            "Cases per 4-year period, by verification tier — 118 cases, 1971–2026",
            title_y=1.34, subtitle_y=1.18)
    ax.text(0, -0.24,
            "Only 2 of 118 cases predate 2004 (1971, 1999); the apparent \"thinness\" of the\n"
            "earlier decades reflects source discoverability and this register's confirmed-\n"
            "enforcement-action scope, not necessarily lower underlying misconduct.",
            transform=ax.transAxes, fontsize=8, color=INK_MUTED, ha="left", va="top")
    plt.savefig("charts/exploratory/volume_by_period.png", facecolor=SURFACE,
                bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    print("wrote charts/exploratory/volume_by_period.png")


# =========================================================================
# Exhibit E2 -- cumulative dollar exposure over time
# =========================================================================
def chart_cumulative_exposure():
    by_year = defaultdict(float)
    for c in cases:
        by_year[c["year"]] += counted_amount(c)
    years = sorted(by_year)
    cum = []
    running = 0
    for y in years:
        running += by_year[y]
        cum.append(running)

    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    ax.plot(years, [v / 1_000_000 for v in cum], color=BLUE, linewidth=2.4, zorder=3)
    ax.fill_between(years, [v / 1_000_000 for v in cum], color=BLUE, alpha=0.10, zorder=2)

    # mark a few step changes worth annotating
    deltas = [(years[i], by_year[years[i]]) for i in range(len(years))]
    top3 = sorted(deltas, key=lambda t: -t[1])[:3]
    for yr, amt in top3:
        idx = years.index(yr)
        ax.annotate(f"+{fmt_dollar(amt)} in {yr}",
                    xy=(yr, cum[idx] / 1_000_000),
                    xytext=(0, 10), textcoords="offset points",
                    fontsize=8, color=INK_SECONDARY, ha="center",
                    fontproperties=SANS_BOLD)
        ax.scatter([yr], [cum[idx] / 1_000_000], color=ORANGE, s=26, zorder=4)

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:.0f}M"))
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    _style_ax(ax)
    _titles(ax, "Tracked exposure has grown in large, uneven steps",
            "Cumulative counted dollar exposure by year of final resolution — $210.0M total",
            title_y=1.24, subtitle_y=1.08)
    plt.savefig("charts/exploratory/cumulative_exposure.png", facecolor=SURFACE,
                bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    print("wrote charts/exploratory/cumulative_exposure.png")


# =========================================================================
# Exhibit E3 -- risk-tier matrix (pervasiveness x recency), bubble = $ exposure
# =========================================================================

# manual nudges for pairings that land on an identical (case_count, recency)
# coordinate as another labeled pairing, so dots and labels don't stack.
# keyed by (agency_group, control_category) -> (dx, xytext_dx, xytext_dy, ha)
_NUDGE = {
    ("Port Authority (NY/NJ)", "Disbursement, Invoice & Change-Order Controls"):
        (-0.12, -8, 10, "right"),
    ("NYSDOT", "MWBE/DBE & Professional-Certification Controls"):
        (0.12, 8, -14, "left"),
    ("MTA", "MWBE/DBE & Professional-Certification Controls"):
        (-0.12, -8, 12, "right"),
    ("Port Authority (NY/NJ)", "Bribery, Kickback & Authorization Controls"):
        (0.12, 8, -16, "left"),
}


def chart_risk_matrix():
    ri = json.load(open("data/risk_index.json"))
    ri = [r for r in ri if r["case_count"] >= 2]  # Recurring + Elevated only

    fig, ax = plt.subplots(figsize=(9.8, 6.6))
    color_map = {"Elevated Focus": SERIOUS, "Recurring Pattern": WARNING}
    for r in ri:
        key = (r["agency_group"], r["control_category"])
        dx = _NUDGE.get(key, (0, 0, 0, "left"))[0]
        x = r["case_count"] + dx
        y = r["recency_share"] * 100
        size = 60 + (r["dollar_exposure"] ** 0.5) / 25
        ax.scatter(x, y, s=size, color=color_map.get(r["risk_tier"], INK_MUTED),
                   alpha=0.75, edgecolors=SURFACE, linewidths=1.2, zorder=3)

    # direct-label the elevated-focus pairs and a couple of notable recurring ones
    labeled = [r for r in ri if r["risk_tier"] == "Elevated Focus"]
    labeled += sorted([r for r in ri if r["risk_tier"] != "Elevated Focus"],
                       key=lambda r: -r["case_count"])[:2]
    for r in labeled:
        key = (r["agency_group"], r["control_category"])
        dx, txt_dx, txt_dy, ha = _NUDGE.get(key, (0, 8, 6, "left"))
        label = f"{r['agency_group']}\n{r['control_category'].split(',')[0].split(' &')[0]}"
        ax.annotate(label, xy=(r["case_count"] + dx, r["recency_share"] * 100),
                    xytext=(txt_dx, txt_dy), textcoords="offset points",
                    fontsize=7.6, color=INK_SECONDARY, linespacing=1.15, ha=ha)

    ax.axhline(50, color=BASELINE, linewidth=0.9, linestyle=(0, (3, 3)), zorder=1)
    ax.text(ax.get_xlim()[1] if ri else 8, 51, "50% recency threshold",
            fontsize=7.5, color=INK_MUTED, ha="right", va="bottom")

    ax.set_xlabel("Pervasiveness — cases in this agency × control-category pairing", fontsize=9,
                  color=INK_SECONDARY)
    ax.set_ylabel("Recency — % of pairing's cases from the last 10 years", fontsize=9,
                  color=INK_SECONDARY)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.grid(color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    _style_ax(ax)
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(BASELINE)

    handles = [plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=c,
                           markersize=9, label=lbl)
               for lbl, c in [("Elevated Focus", SERIOUS), ("Recurring Pattern", WARNING)]]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9)
    _titles(ax, "Where scrutiny has concentrated: the risk-tier rubric, plotted",
            "Bubble size = dollar exposure — Isolated Precedent pairings (42, all case_count=1) omitted for readability",
            title_y=1.13, subtitle_y=1.045)
    plt.savefig("charts/exploratory/risk_matrix.png", facecolor=SURFACE,
                bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    print("wrote charts/exploratory/risk_matrix.png")


# =========================================================================
# Exhibit E4 -- repeat-entity ("recidivism") summary table
# =========================================================================
REPEAT_ENTITIES = [
    ("Thomas Delaney / Over Rock Construction LLC", "NYPA",
     "2015, 2016", "Linked (scheme_family)"),
    ("Dmyles Inc.", "DASNY",
     "2024, 2024", "Linked (scheme_family)"),
    ("Spectrum Painting Corp. / Tower Maintenance Corp.", "MTA",
     "2019, 2021, 2021", "Linked (scheme_family)"),
    ("Henry Chlupsa", "NYC DEP",
     "2018, 2020", "Linked (scheme_family)"),
    ("Steven Aiello", "SUNY Poly",
     "2018, 2026", "NOT linked — 2 slugs, 1 scandal"),
]


def chart_repeat_entities():
    fig, ax = plt.subplots(figsize=(9.8, 3.5))
    ax.axis("off")
    ax.set_facecolor(SURFACE)
    fig.patch.set_facecolor(SURFACE)

    _titles(ax, "Entities named in more than one independently-verified case",
            "Free-text name match across the `entities` field, 118-case register — 5 clusters found",
            title_y=1.26, subtitle_y=1.09)

    col_x = [0.0, 0.46, 0.66, 0.83]
    headers = ["Entity", "Agency", "Case years", "Dedup status"]
    y0 = 0.90
    for cx, h in zip(col_x, headers):
        ax.text(cx, y0, h, fontsize=9, fontproperties=SANS_BOLD, color=INK_SECONDARY,
                transform=ax.transAxes)
    ax.plot([0, 1], [y0 - 0.06, y0 - 0.06], color=BASELINE, linewidth=0.9,
            transform=ax.transAxes)

    row_h = 0.155
    for i, (name, agency, years, status) in enumerate(REPEAT_ENTITIES):
        y = y0 - 0.17 - i * row_h
        color = GOOD if status.startswith("Linked") else SERIOUS
        ax.text(col_x[0], y, name, fontsize=8.4, color=INK, transform=ax.transAxes, va="top")
        ax.text(col_x[1], y, agency, fontsize=8.4, color=INK_SECONDARY, transform=ax.transAxes, va="top")
        ax.text(col_x[2], y, years, fontsize=8.4, color=INK_MUTED, transform=ax.transAxes,
                va="top", fontproperties=MONO)
        ax.text(col_x[3], y, status, fontsize=8.4, color=color, transform=ax.transAxes, va="top")

    ax.text(0, -0.14,
            "Heuristic text match, not verified entity resolution — flagged for manual confirmation before use as a finding.\n"
            "4 of 5 clusters were already correctly scheme_family-linked in the existing dedup logic (a useful QA check, not new risk).\n"
            "The 5th (Aiello, Buffalo Billion) uses two different scheme_family slugs for what may be one broader scandal — worth a\n"
            "one-time review of whether that's an intentional distinction (different individuals' separate restitution amounts) or a\n"
            "naming inconsistency to fix.",
            transform=ax.transAxes, fontsize=7.6, color=INK_MUTED, ha="left", va="top")

    plt.savefig("charts/exploratory/repeat_entities.png", facecolor=SURFACE,
                bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote charts/exploratory/repeat_entities.png")


if __name__ == "__main__":
    chart_volume_by_period()
    chart_cumulative_exposure()
    chart_risk_matrix()
    chart_repeat_entities()
