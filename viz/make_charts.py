#!/usr/bin/env python3
"""Turns the Hive query results (results/*.tsv) into PNG charts (results/charts/).

usage: python3 viz/make_charts.py [results_dir]
"""
import csv
import os
import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

RESULTS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "results")
CHARTS = os.path.join(RESULTS, "charts")

# Validated categorical palette (fixed order) + text/grid tokens
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE, TEXT, TEXT_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
ANNOUNCE = "2022-09-08T17"  # Buckingham Palace announcement at 17:30 UTC falls in this hour

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "text.color": TEXT, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold",
    "axes.titlesize": 13, "axes.titlelocation": "left", "font.size": 10, "legend.frameon": False,
})


def read(name):
    path = os.path.join(RESULTS, name + ".tsv")
    if not os.path.exists(path):
        print("skip (missing):", path)
        return []
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    if not rows:
        return []
    # Hive may prefix headers with the table alias ("p.hour") - keep the bare column name
    header = [h.split(".")[-1] for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:] if len(r) == len(header)]


def human(x, _pos=None):
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(x) >= div:
            return f"{x / div:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{x:.0f}"


def hour_tick(h):
    # "2022-09-08T17" -> "17h" (and the date at midnight)
    return h[5:10] + "\n00h" if h.endswith("T00") else h[-2:] + "h"


def save(fig, name):
    os.makedirs(CHARTS, exist_ok=True)
    out = os.path.join(CHARTS, name + ".png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def mark_announcement(ax, hours, y=0.5):
    """Dashed line at the announcement; label sits left of the line at axes-height y."""
    if ANNOUNCE in hours:
        x = hours.index(ANNOUNCE) + 0.5
        ax.axvline(x, color=TEXT_2, linewidth=1, linestyle=(0, (3, 3)))
        ax.text(x - 0.2, y, "death announced\n17:30 UTC", transform=ax.get_xaxis_transform(), ha="right",
                va="center", fontsize=9, color=TEXT_2)


def chart_timeline():
    rows = read("q2_story_timeline")
    if not rows:
        return
    series = defaultdict(dict)
    for r in rows:
        series[r["article"]][r["hour"]] = int(r["views"])
    hours = sorted({h for s in series.values() for h in s})
    # 4 biggest stories by peak, so every line can be direct-labelled
    top = sorted(series, key=lambda a: -max(series[a].values()))[:4]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for i, art in enumerate(top):
        ys = [series[art].get(h, 0) for h in hours]
        ax.plot(range(len(hours)), ys, color=SERIES[i], linewidth=2, label=art)
    main = series[top[0]]
    peak_h = max(main, key=main.get)
    ax.annotate(f"{top[0]}: {human(main[peak_h])} views in one hour", (hours.index(peak_h), main[peak_h]),
                xytext=(-12, 0), textcoords="offset points", ha="right", va="center", fontsize=9, color=TEXT)
    first = hours.index("2022-09-08T12")
    ax.annotate("12h: story breaks\n(Palace: doctors concerned)", (first, series[top[0]].get(hours[first], 1)),
                xytext=(-80, 40), textcoords="offset points", ha="right", fontsize=9, color=TEXT,
                arrowprops=dict(arrowstyle="-", color=TEXT_2, linewidth=0.8))
    ax.set_yscale("log")
    ax.set_ylim(bottom=100)
    ax.yaxis.set_major_formatter(FuncFormatter(human))
    ax.set_xticks(range(0, len(hours), 2))
    ax.set_xticklabels([hour_tick(h) for h in hours[::2]])
    ax.set_ylabel("views per hour (log scale)")
    ax.set_title("English Wikipedia: hourly views of the top stories, 7-8 Sep 2022 (UTC)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=4)
    mark_announcement(ax, hours, y=0.3)
    save(fig, "1_story_timeline")


def chart_spikes_per_hour():
    rows = read("q3_spikes_per_hour")
    if not rows:
        return
    hours = [r["hour"] for r in rows]
    vals = [int(r["total_excess_views"]) for r in rows]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(range(len(hours)), vals, color=SERIES[0], width=0.8, edgecolor=SURFACE, linewidth=1)
    ax.yaxis.set_major_formatter(FuncFormatter(human))
    ax.set_xticks(range(0, len(hours), 2))
    ax.set_xticklabels([hour_tick(h) for h in hours[::2]])
    ax.set_ylabel("extra views on spiking articles")
    ax.set_title("News intensity per hour: extra readers drawn by detected spikes")
    ax.grid(axis="x", visible=False)
    peak = max(range(len(vals)), key=lambda k: vals[k])
    ax.annotate(f"{human(vals[peak])} extra views\n{rows[peak]['spikes']} articles spiking",
                (peak + 0.4, vals[peak] * 0.97), xytext=(40, -30), textcoords="offset points", fontsize=9,
                arrowprops=dict(arrowstyle="-", color=TEXT_2, linewidth=0.8))
    mark_announcement(ax, hours, y=0.6)
    save(fig, "2_spikes_per_hour")


def chart_top_stories():
    rows = read("q1_top_stories")[:12]
    if not rows:
        return
    rows = rows[::-1]
    labels = [f"{r['article']}  ({r['lang']})" for r in rows]
    vals = [int(r["max_excess_views"]) for r in rows]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.barh(range(len(rows)), vals, color=SERIES[0], height=0.72, edgecolor=SURFACE, linewidth=1)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels)
    ax.xaxis.set_major_formatter(FuncFormatter(human))
    ax.grid(axis="y", visible=False)
    for i, (v, r) in enumerate(zip(vals, rows)):
        ax.text(v, i, f"  {human(v)}  · first {r['first_detected'][-2:]}h", va="center", fontsize=8.5, color=TEXT_2)
    ax.set_xlim(0, max(vals) * 1.25)
    ax.set_xlabel("largest hourly excess views (views above baseline)")
    ax.set_title("Biggest stories detected (all languages)")
    save(fig, "3_top_stories")


def chart_language_traffic():
    rows = read("q5_traffic_by_language")
    if not rows:
        return
    series = defaultdict(dict)
    for r in rows:
        series[r["lang"]][r["hour"]] = int(r["total_views"])
    hours = sorted({h for s in series.values() for h in s})
    top = sorted(series, key=lambda l: -sum(series[l].values()))[:4]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for i, lang in enumerate(top):
        ys = [series[lang].get(h, 0) for h in hours]
        ax.plot(range(len(hours)), ys, color=SERIES[i], linewidth=2, label=lang)
        ax.annotate(lang, (len(hours) - 1, ys[-1]), xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=9, color=TEXT)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(human))
    ax.set_xticks(range(0, len(hours), 2))
    ax.set_xticklabels([hour_tick(h) for h in hours[::2]])
    ax.set_ylabel("article views per hour (log scale)")
    ax.set_title("Total article traffic of the four largest Wikipedia editions (UTC)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=4)
    save(fig, "4_language_traffic")


if __name__ == "__main__":
    chart_timeline()
    chart_spikes_per_hour()
    chart_top_stories()
    chart_language_traffic()
