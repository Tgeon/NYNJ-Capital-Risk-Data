"""
charts.py -- builds the 8 charts used in the README and the tracker.

Palette: dataviz skill's validated default (references/palette.md).
  categorical slot 1 (blue)   #2a78d6
  categorical slot 2 (orange) #eb6834
  categorical slot 3 (aqua)   #1baf7a
  status: good #0ca30c / warning #fab219 / serious #ec835a
Chart surface: #fcfcfb (light). Ink: primary #0b0b0b, secondary #52514e,
muted #898781, gridline #e1e0d9, baseline #c3c2b7.
"""

import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as mticker

# ---- fonts -----------------------------------------------------------
fm.fontManager.addfont("fonts/WorkSans-Regular.ttf")
fm.fontManager.addfont("fonts/WorkSans-Bold.ttf")
fm.fontManager.addfont("fonts/IBMPlexMono-Regular.ttf")
SANS = fm.FontProperties(fname="fonts/WorkSans-Regular.ttf").get_name()
SANS_BOLD = fm.FontProperties(fname="fonts/WorkSans-Bold.ttf").get_name()
MONO = fm.FontProperties(fname="fonts/IBMPlexMono-Regular.ttf").get_name()
plt.rcParams["font.family"] = SANS

# ---- palette -----------------------------------------------------------
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


def _style_ax(ax):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9.5)


BOLD = fm.FontProperties(fname="fonts/WorkSans-Bold.ttf")


def _titles(ax, title, subtitle, title_y=1.22, subtitle_y=1.06):
    """Title above subtitle, both in axes-fraction coords so ordering is exact."""
    ax.text(0, title_y, title, transform=ax.transAxes, fontsize=12.5,
             fontproperties=BOLD, color=INK, ha="left", va="bottom")
    ax.text(0, subtitle_y, subtitle, transform=ax.transAxes, fontsize=9,
             color=INK_SECONDARY, ha="left", va="bottom")


def fmt_dollar(x, compact=True):
    if x >= 1_000_000:
        v = x / 1_000_000
        return f"${v:.0f}M" if v == int(v) else f"${v:.1f}M"
    if x >= 1_000:
        return f"${x/1_000:.0f}K"
    return f"${x:.0f}"


# =========================================================================
# Chart 1 -- exposure by capital-project type
# =========================================================================
def chart_by_type():
    data = json.load(open("data/index_by_type.json"))
    data = sorted(data, key=lambda d: d["dollar_exposure"])
    labels = [d["project_type"] for d in data]
    values = [d["dollar_exposure"] for d in data]
    counts = [d["case_count"] for d in data]

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    bars = ax.barh(labels, values, height=0.62, color=BLUE, zorder=3)
    for bar, v, c in zip(bars, values, counts):
        ax.text(v + max(values) * 0.02, bar.get_y() + bar.get_height() / 2,
                 f"{fmt_dollar(v)}  ({c} case{'s' if c != 1 else ''})",
                 va="center", ha="left", fontsize=9, color=INK, family=MONO)

    ax.set_xlim(0, max(values) * 1.34)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_dollar(x)))
    _titles(ax, "Enforcement exposure by capital-project type",
            "Dollar value of NY & NJ capital contracts implicated in a confirmed or probable\nenforcement action, by project type (n=70 unique cases)",
            title_y=1.14, subtitle_y=1.02)
    _style_ax(ax)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout(rect=[0, 0, 1, 0.86])
    plt.savefig("charts/exposure_by_type.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close()


# =========================================================================
# Chart 2 -- exposure by NY/NJ region
# =========================================================================
def chart_by_region():
    data = json.load(open("data/index_by_region.json"))
    data = sorted(data, key=lambda d: d["dollar_exposure"])
    labels = [d["region_group"] for d in data]
    values = [d["dollar_exposure"] for d in data]
    counts = [d["case_count"] for d in data]

    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=200)
    bars = ax.barh(labels, values, height=0.6, color=BLUE, zorder=3)
    for bar, v, c in zip(bars, values, counts):
        ax.text(v + max(values) * 0.02, bar.get_y() + bar.get_height() / 2,
                 f"{fmt_dollar(v)}  ({c} case{'s' if c != 1 else ''})",
                 va="center", ha="left", fontsize=9.5, color=INK, family=MONO)

    ax.set_xlim(0, max(values) * 1.35)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_dollar(x)))
    _titles(ax, "Enforcement exposure by region",
            "New York City leads on both case count and dollars; Northern NJ (Port Authority,\nmunicipal redevelopment) has the next-most cases but far smaller dollar figures each",
            title_y=1.20, subtitle_y=1.04)
    _style_ax(ax)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout(rect=[0, 0, 1, 0.82])
    plt.savefig("charts/exposure_by_region.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close()


# =========================================================================
# Chart 3 -- verification status (single stacked bar, status colors)
# =========================================================================
def chart_verification():
    summary = json.load(open("data/summary.json"))["verification"]
    segments = [
        ("Confirmed", summary["confirmed"], summary["confirmed_pct"], GOOD),
        ("Probable", summary["probable"], summary["probable_pct"], WARNING),
        ("Uncorroborated", summary["uncorroborated"], summary["uncorroborated_pct"], SERIOUS),
    ]

    fig = plt.figure(figsize=(7.2, 2.55), dpi=200, facecolor=SURFACE)
    fig.text(0.015, 0.93, "Verification status of the 70-case dataset",
              fontsize=12.5, fontproperties=BOLD, color=INK, ha="left", va="top")
    ax = fig.add_axes([0.015, 0.46, 0.97, 0.26])  # [left, bottom, width, height] fig-fraction

    # Pass 1: draw all bar segments first so no label is later covered by a
    # bar drawn on top of it.
    left = 0
    bounds = []
    for name, n, pct, color in segments:
        ax.barh([0], [pct], left=left, height=0.9, color=color, zorder=3,
                edgecolor=SURFACE, linewidth=2)
        bounds.append((name, n, pct, color, left))
        left += pct

    # Pass 2: labels. Segments wide enough (>=12%) get a centered label
    # inside the bar; a narrow segment gets a below-bar callout with a
    # leader line, so it never collides with the next segment's label.
    for name, n, pct, color, seg_left in bounds:
        center = seg_left + pct / 2
        if pct >= 12:
            ax.text(center, 0, f"{name}\n{pct}%  (n={n})", ha="center", va="center",
                    fontsize=9.5, color="white" if color != WARNING else INK,
                    fontproperties=BOLD, zorder=4)
        else:
            ax.plot([center, center], [-0.55, -1.15], color=INK_MUTED, linewidth=0.9,
                    zorder=4, clip_on=False)
            ax.text(center, -1.35, f"{name} {pct}% (n={n})", ha="center", va="top",
                    fontsize=9.2, color=INK, zorder=4, clip_on=False)
    ax.set_xlim(0, 100)
    ax.set_ylim(-1, 1)
    ax.axis("off")
    fig.text(0.015, 0.15, "Confirmed = corroborated by a source independent of the primary enforcement-agency release\n"
                           "(a different agency's own release, a court docket/opinion, or contemporaneous independent press).\n"
                           f"{summary['duplicate_rate_pct']}% of the 78 raw enforcement records pulled (NY + NJ) were later-stage duplicates\n"
                           "of an already-counted case and were excluded before this count.",
              fontsize=8.5, color=INK_SECONDARY, ha="left", va="top")
    plt.savefig("charts/verification_status.png", facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close()


# =========================================================================
# Chart 4 -- enforcement actions by year and stage (stacked bar)
# =========================================================================
def chart_timeline():
    cases = json.load(open("data/cases_unique.json"))
    import collections
    by_year = collections.defaultdict(lambda: collections.Counter())
    for c in cases:
        year = int(c["date"][:4])
        # bucket into 4-year bins for readability across a 2008-2026 span
        bin_start = 4 * (year // 4)
        label = f"{bin_start}-{bin_start+3}"
        by_year[label][c["stage_bucket"]] += 1

    order = sorted(by_year.keys())
    other_stages = ["Charged / indicted", "IG finding / administrative", "Other", "Dismissed / vacated"]

    crim = [by_year[y]["Criminal conviction / plea / sentence"] for y in order]
    settle = [by_year[y]["Settlement / DPA-NPA"] for y in order]
    other = [sum(by_year[y][s] for s in other_stages) for y in order]

    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=200)
    x = range(len(order))
    ax.bar(x, crim, color=BLUE, label="Criminal conviction / plea / sentence", zorder=3, width=0.62)
    ax.bar(x, settle, bottom=crim, color=ORANGE, label="Settlement / deferred or non-prosecution agreement", zorder=3, width=0.62)
    bottom2 = [a + b for a, b in zip(crim, settle)]
    ax.bar(x, other, bottom=bottom2, color=AQUA, label="Charged / IG finding / other", zorder=3, width=0.62)

    ax.set_xticks(list(x))
    ax.set_xticklabels(order, fontsize=9.5, color=INK_SECONDARY)
    ax.set_ylim(0, max(bottom2[i] + other[i] for i in range(len(order))) * 1.65)
    _titles(ax, "Enforcement actions by 4-year period and type",
            "70 unique cases, 2005-2026. Criminal cases dominate the confirmed record; a growing share\nof recent NY and NJ findings are resolved administratively (IG/SCI reports) rather than prosecuted.",
            title_y=1.30, subtitle_y=1.12)
    _style_ax(ax)
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK_SECONDARY,
              bbox_to_anchor=(0.0, 1.0), ncol=1)
    plt.tight_layout(rect=[0, 0, 1, 0.76])
    plt.savefig("charts/timeline_by_stage.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close()


# =========================================================================
# Chart 5 -- exposure by internal-control category
# =========================================================================
def chart_by_control_category():
    data = json.load(open("data/controls_by_category.json"))
    data = sorted(data, key=lambda d: d["dollar_exposure"])
    labels = [d["control_category"].replace(" Controls", "") for d in data]
    values = [d["dollar_exposure"] for d in data]
    counts = [d["case_count"] for d in data]

    fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
    bars = ax.barh(labels, values, height=0.6, color=BLUE, zorder=3)
    for bar, v, c in zip(bars, values, counts):
        ax.text(v + max(values) * 0.02, bar.get_y() + bar.get_height() / 2,
                 f"{fmt_dollar(v)}  ({c} case{'s' if c != 1 else ''})",
                 va="center", ha="left", fontsize=9, color=INK, family=MONO)

    ax.set_xlim(0, max(values) * 1.38)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_dollar(x)))
    _titles(ax, "Exposure by internal-control category",
            "Dollar exposure grouped by the PRIMARY control that failed in each case (n=70; one\ncategory per case -- see controls.py for the per-case assignment and rationale)",
            title_y=1.16, subtitle_y=1.02)
    _style_ax(ax)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout(rect=[0, 0, 1, 0.84])
    plt.savefig("charts/exposure_by_control_category.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close()


# =========================================================================
# Chart 6 -- control-deficiency severity (single stacked bar, status colors)
# =========================================================================
def chart_severity():
    summary = json.load(open("data/severity_summary.json"))["by_severity"]
    color_map = {"Material Weakness": SERIOUS, "Significant Deficiency": WARNING, "Control Deficiency": GOOD}
    segments = [(row["severity"], row["case_count"], row["case_pct"], row["dollar_exposure"],
                 color_map[row["severity"]]) for row in summary]

    fig = plt.figure(figsize=(7.2, 2.75), dpi=200, facecolor=SURFACE)
    fig.text(0.015, 0.94, "Control-deficiency severity of the 70-case dataset",
              fontsize=12.5, fontproperties=BOLD, color=INK, ha="left", va="top")
    ax = fig.add_axes([0.015, 0.50, 0.97, 0.24])

    left = 0
    bounds = []
    for name, n, pct, dollars, color in segments:
        ax.barh([0], [pct], left=left, height=0.9, color=color, zorder=3,
                edgecolor=SURFACE, linewidth=2)
        bounds.append((name, n, pct, dollars, color, left))
        left += pct

    for name, n, pct, dollars, color, seg_left in bounds:
        center = seg_left + pct / 2
        label = f"{name}\n{pct}%  (n={n}, {fmt_dollar(dollars)})"
        if pct >= 20:
            ax.text(center, 0, label, ha="center", va="center", fontsize=9.2,
                    color="white" if color != WARNING else INK, fontproperties=BOLD, zorder=4)
        else:
            ax.plot([center, center], [-0.55, -1.15], color=INK_MUTED, linewidth=0.9,
                    zorder=4, clip_on=False)
            ax.text(center, -1.35, f"{name} {pct}% (n={n}, {fmt_dollar(dollars)})", ha="center",
                    va="top", fontsize=8.8, color=INK, zorder=4, clip_on=False)
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.1, 1)
    ax.axis("off")
    fig.text(0.015, 0.14,
              "Severity = magnitude of the disclosed dollar figure x pervasiveness (whether the same agency shows\n"
              "the same control-category failure repeatedly). Every case here already cleared the bar of a public\n"
              "enforcement action, so this mix is not a representative audit sample -- see Methodology.",
              fontsize=8.3, color=INK_SECONDARY, ha="left", va="top")
    plt.savefig("charts/severity_distribution.png", facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close()


# =========================================================================
# Chart 7 -- variance waterfall between the two most complete 4-year periods
# =========================================================================
def chart_variance_waterfall():
    v = json.load(open("data/variance_drivers.json"))
    drivers = v["drivers"]

    INCREASE = BLUE
    DECREASE = ORANGE
    TOTAL_COLOR = INK_SECONDARY

    labels = [v["compare_from"]] + [d["control_category"].replace(" Controls", "") for d in drivers] + [v["compare_to"]]
    n = len(labels)

    cumulative = v["total_from"]
    bar_bottoms, bar_heights, bar_colors = [0], [v["total_from"]], [TOTAL_COLOR]
    for d in drivers:
        delta = d["delta"]
        if delta >= 0:
            bar_bottoms.append(cumulative)
            bar_heights.append(delta)
            bar_colors.append(INCREASE)
        else:
            bar_bottoms.append(cumulative + delta)
            bar_heights.append(-delta)
            bar_colors.append(DECREASE)
        cumulative += delta
    bar_bottoms.append(0)
    bar_heights.append(v["total_to"])
    bar_colors.append(TOTAL_COLOR)

    fig, ax = plt.subplots(figsize=(7.4, 4.4), dpi=200)
    x = range(n)
    bars = ax.bar(x, bar_heights, bottom=bar_bottoms, color=bar_colors, width=0.62, zorder=3)

    # connector lines between bars (running-total steps)
    running = v["total_from"]
    for i, d in enumerate(drivers):
        running_next = running + d["delta"]
        top = max(running, running_next)
        ax.plot([i + 0.31, i + 1 - 0.31], [top if d["delta"] >= 0 else running, top if d["delta"] >= 0 else running],
                color=BASELINE, linewidth=0.9, zorder=2, linestyle=(0, (2, 2)))
        running = running_next

    for i, (bot, h, d) in enumerate(zip(bar_bottoms, bar_heights, [None] + drivers + [None])):
        val = h if d is None else d["delta"]
        label = fmt_dollar(bar_heights[i]) if d is None else f"{'+' if val >= 0 else '-'}{fmt_dollar(abs(val))}"
        ax.text(i, bot + h + max(bar_heights) * 0.025, label, ha="center", va="bottom",
                fontsize=8.6, color=INK, family=MONO)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8.2, color=INK_SECONDARY, rotation=20, ha="right")
    ax.set_ylim(0, max(v["total_from"], v["total_to"], max(b + h for b, h in zip(bar_bottoms, bar_heights))) * 1.18)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda val, _: fmt_dollar(val)))
    _titles(ax, f"Exposure bridge: {v['compare_from']} → {v['compare_to']}",
            f"Net variance {fmt_dollar(v['total_delta']) if v['total_delta']>=0 else '-'+fmt_dollar(abs(v['total_delta']))} "
            f"({v['total_delta_pct']}%), decomposed by control-category driver",
            title_y=1.20, subtitle_y=1.05)
    _style_ax(ax)
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout(rect=[0, 0, 1, 0.80])
    plt.savefig("charts/variance_waterfall.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close()


# =========================================================================
# Chart 8 -- exposure by state (NY / NJ / bi-state Port Authority)
# =========================================================================
def chart_by_state():
    data = json.load(open("data/index_by_state.json"))
    label_map = {"NY": "New York", "NJ": "New Jersey", "NY/NJ": "Port Authority (bi-state)"}
    data = sorted(data, key=lambda d: d["dollar_exposure"])
    labels = [label_map.get(d["state"], d["state"]) for d in data]
    values = [d["dollar_exposure"] for d in data]
    counts = [d["case_count"] for d in data]
    color_map = {"New York": BLUE, "New Jersey": ORANGE, "Port Authority (bi-state)": AQUA}
    bar_colors = [color_map[l] for l in labels]

    fig = plt.figure(figsize=(7.2, 3.15), dpi=200, facecolor=SURFACE)
    fig.text(0.06, 0.95, "Exposure by state", fontsize=12.5, fontproperties=BOLD,
              color=INK, ha="left", va="top")
    fig.text(0.06, 0.83,
              "New York's own oversight sources (led by ig.ny.gov) are unusually prolific; New Jersey\n"
              "has fewer dedicated capital-project IG postings but a broadly similar per-case dollar scale",
              fontsize=9, color=INK_SECONDARY, ha="left", va="top")
    ax = fig.add_axes([0.06, 0.14, 0.90, 0.42])  # [left, bottom, width, height] fig-fraction

    bars = ax.barh(labels, values, height=0.5, color=bar_colors, zorder=3)
    for bar, v, c in zip(bars, values, counts):
        ax.text(v + max(values) * 0.02, bar.get_y() + bar.get_height() / 2,
                 f"{fmt_dollar(v)}  ({c} case{'s' if c != 1 else ''})",
                 va="center", ha="left", fontsize=9.5, color=INK, family=MONO)

    ax.set_xlim(0, max(values) * 1.38)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_dollar(x)))
    _style_ax(ax)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    plt.savefig("charts/exposure_by_state.png", facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close()


if __name__ == "__main__":
    chart_by_type()
    chart_by_region()
    chart_verification()
    chart_timeline()
    chart_by_control_category()
    chart_severity()
    chart_variance_waterfall()
    chart_by_state()
    print("Wrote 8 charts to charts/")
