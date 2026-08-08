#!/usr/bin/env python3
"""生成报告图表（中文标注，PNG 300dpi）。
依赖 output/stats.json（由 analyze_contents.py 生成）。
用法: python3 src/make_charts.py
"""
import json, os, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = os.path.join(ROOT, "output", "stats.json")
OUTDIR = os.path.join(ROOT, "output", "charts")

for name in ["PingFang HK", "Hiragino Sans GB", "Noto Sans CJK SC", "STHeiti", "Arial Unicode MS", "SimHei"]:
    if any(f.name == name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [name]
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150

TYPE_CN = {"answer": "回答", "article": "文章", "pin": "想法", "zvideo": "视频", "question": "提问"}
COLORS = {"answer": "#e8614f", "article": "#3b6fd4", "pin": "#f2a93b", "zvideo": "#7a4fc4", "question": "#4caf92"}


def save(fig, name):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, name)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("已生成", path)


def fig1_type_dist(s):
    td = s["type_dist"]
    labels = [TYPE_CN[k] for k in td]
    counts = [v["count"] for v in td.values()]
    pcts = [v["pct"] for v in td.values()]
    colors = [COLORS[k] for k in td]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(labels, counts, color=colors, width=0.55)
    for b, c, p in zip(bars, counts, pcts):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.2, f"{c} 条\n{p}%",
                ha="center", va="bottom", fontsize=12)
    ax.set_ylim(0, max(counts) * 1.25)
    ax.set_ylabel("创作数量（条）")
    ax.set_title("创作类型分布（共 91 条）", fontsize=14, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig1_type_dist.png")


def fig2_top10_fav(s):
    rows = list(reversed(s["top10_fav"]))
    titles = [r["title"] for r in rows]
    short = [t[:16] + ("…" if len(t) > 16 else "") for t in titles]
    vals = [r["fav"] for r in rows]
    colors = [COLORS["answer"] if r["type"] == "回答" else COLORS["article"] if r["type"] == "文章" else COLORS["pin"] for r in rows]
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    bars = ax.barh(short, vals, color=colors, height=0.62)
    for b, v, r in zip(bars, vals, rows):
        ax.text(v + 6, b.get_y() + b.get_height() / 2, f"{v} 藏", va="center", fontsize=10)
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_xlabel("收藏数")
    ax.set_title("收藏 Top 10（红=回答，蓝=文章）", fontsize=14, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig2_top10_fav.png")


def fig3_timeline(s):
    md = s["month_type_dist"]
    months = list(md.keys())
    types = ["article", "answer", "pin"]
    bottom = [0] * len(months)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    for t in types:
        counts = [md[m].get(t, 0) for m in months]
        ax.bar(months, counts, bottom=bottom, width=0.68, label=TYPE_CN[t], color=COLORS[t])
        bottom = [a + b for a, b in zip(bottom, counts)]
    ax.set_ylabel("创作数量（条）")
    months_all = sorted(s["month_dist"])
    ax.set_title(f"月度创作时间线（{months_all[0]} 至 {months_all[-1]}）", fontsize=14, pad=12)
    ax.legend(frameon=False, ncol=3)
    ax.tick_params(axis="x", rotation=55, labelsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig3_timeline.png")


def fig4_cat_perf(s):
    rows = sorted(s["by_cat"].items(), key=lambda x: x[1]["fav_mean"])
    cats = [k for k, _ in rows]
    means = [v["fav_mean"] for v, _ in [(v, k) for k, v in rows]]
    counts = [v["n"] for v, _ in [(v, k) for k, v in rows]]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    bars = ax.barh(cats, means, color=["#3b6fd4", "#7a4fc4", "#f2a93b", "#e8614f"], height=0.55)
    for b, m, n in zip(bars, means, counts):
        ax.text(m + 0.8, b.get_y() + b.get_height() / 2, f"{m:.1f} 藏/篇（{n} 篇）", va="center", fontsize=10)
    ax.set_xlim(0, max(means) * 1.3)
    ax.set_xlabel("平均收藏数（藏/篇）")
    ax.set_title("内容主题 × 平均收藏：工具教程遥遥领先", fontsize=14, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig4_cat_perf.png")



def fig5_series(s):
    rows = [x for x in s["series"] if x["n"] >= 2][:8]
    rows = list(reversed(rows))
    names = [x["name"] for x in rows]
    means = [x["fav_mean"] for x in rows]
    gaps = [x["days_since_last"] for x in rows]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.barh(names, means, color="#3b6fd4", height=0.55)
    for b, m, g, x in zip(bars, means, gaps, rows):
        tag = "更新中" if g <= 60 else f"断更 {g // 30} 个月"
        ax.text(m + 0.8, b.get_y() + b.get_height() / 2, f"{m:.1f} 藏/篇 · {x['n']} 篇 · {tag}",
                va="center", fontsize=10)
    ax.set_xlim(0, max(means) * 1.45)
    ax.set_xlabel("系列单篇平均收藏（藏/篇）")
    ax.set_title("创作系列 × 平均收藏（篇数 ≥ 2 的系列）", fontsize=14, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig5_series.png")


def fig6_cum_fav(s):
    items = json.load(open(os.path.join(ROOT, "data", "contents.json"), encoding="utf-8"))
    items.sort(key=lambda x: x.get("CreatedAt") or 0)
    dates, cum, acc = [], [], 0
    for it in items:
        acc += it.get("FavoriteCount") or 0
        d = datetime.datetime.fromtimestamp(it.get("CreatedAt") or 0)
        dates.append(d)
        cum.append(acc)
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(dates, cum, color="#3b6fd4", lw=2.2)
    ax.fill_between(dates, cum, color="#3b6fd4", alpha=0.12)
    ax.axvline(datetime.datetime(2025, 1, 1), color="#999", ls="--", lw=1)
    ax.text(datetime.datetime(2025, 1, 2), ax.get_ylim()[0] + 250, "2025-01", color="#666", fontsize=9)
    ax.set_ylabel("累计收藏")
    ax.set_title(f"收藏资产累积曲线（按创作时间累加，截至 {s['as_of']}）", fontsize=14, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig6_cum_fav.png")

def fig7_matrix(s):
    cats = ["工具教程", "概念科普", "论文解读", "其他/随笔"]
    types = ["answer", "article", "pin"]
    cn = [TYPE_CN[t] for t in types]
    grid = [[s["matrix"].get(c, {}).get(t, {}).get("n", 0) for t in types] for c in cats]
    means = [[s["matrix"].get(c, {}).get(t, {}).get("fav_mean", 0) for t in types] for c in cats]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    import numpy as np
    im = ax.imshow(grid, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(cn))); ax.set_xticklabels(cn)
    ax.set_yticks(range(len(cats))); ax.set_yticklabels(cats)
    for i in range(len(cats)):
        for j in range(len(types)):
            n = grid[i][j]
            label = f"{n} 篇\n藏均 {means[i][j]:.1f}" if n else "0 篇"
            color = "white" if n > 12 else "#1f2328"
            ax.text(j, i, label, ha="center", va="center", fontsize=10.5, color=color)
    ax.set_title("内容矩阵：主题 × 类型（篇数与单篇平均收藏）", fontsize=14, pad=12)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    save(fig, "fig7_matrix.png")

def fig8_trend(s):
    items = {i.get("Url"): i.get("Title", "") for i in json.load(open(os.path.join(ROOT, "data", "contents.json"), encoding="utf-8"))}
    deltas = s["snapshot_info"]["delta_items"][:8]
    titles = [(items.get(d["url"], d["url"][:24]))[:18] + ("…" if len(items.get(d["url"], "")) > 18 else "") for d in deltas]
    vals = [d["fav"] for d in deltas]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    bars = ax.barh(titles[::-1], vals[::-1], color="#3b6fd4", height=0.6)
    for b, v in zip(bars, vals[::-1]):
        ax.text(v + 0.4, b.get_y() + b.get_height() / 2, f"+{v}", va="center", fontsize=10)
    ax.set_xlabel("区间新增收藏")
    ax.set_title(f"跨期新增收藏 Top（{s['snapshot_info']['first']} → {s['snapshot_info']['last']}）", fontsize=14, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig8_trend.png")


def main():
    s = json.load(open(STATS, encoding="utf-8"))
    fig1_type_dist(s)
    fig2_top10_fav(s)
    fig3_timeline(s)
    fig4_cat_perf(s)
    fig5_series(s)
    fig6_cum_fav(s)
    fig7_matrix(s)
    if s.get("snapshot_info", {}).get("snapshots", 1) >= 2:
        fig8_trend(s)


if __name__ == "__main__":
    main()
