#!/usr/bin/env python3
"""创作复盘分析脚本：读取 data/contents.json 缓存，输出全量统计到 output/stats.json。
新增能力：系列分析（断更检测）、收藏速率与头部集中度、星期/标题特征、历史快照。
用法: python3 src/analyze_contents.py
"""
import json, os, datetime, statistics
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "contents.json")
HISTORY = os.path.join(ROOT, "data", "history.json")
OUT = os.path.join(ROOT, "output", "stats.json")
FETCH_META = json.load(open(os.path.join(ROOT, "data", "fetch_meta.json"), encoding="utf-8"))
NOW = datetime.datetime.fromisoformat(FETCH_META["fetched_at"])
TODAY = NOW.strftime("%Y-%m-%d")

TYPE_LABEL = {"answer": "回答", "article": "文章", "pin": "想法", "zvideo": "视频", "question": "提问"}
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# ---- 主题分类（加权关键词打分，标题命中额外 +1；0 分归入其他/随笔）----
CAT_RULES = [
    ("工具教程", {"工具": 1, "教程": 2, "配置": 2, "指南": 2, "安装": 2, "插件": 2, "开源": 1,
                  "科研绘图": 2, "作图": 2, "绘图": 2, "matlab": 2, "zotero": 2, "latex": 2,
                  "pix2tex": 2, "pdfmathtranslate": 2, "wannsymm": 2, "excel": 1, "origin": 1,
                  "deepseek": 1, "opencode": 1, "代码": 1, "编程": 1, "写作": 2, "镜像": 1,
                  "drop": 1, "模板": 1}),
    ("概念科普", {"理解": 1, "科普": 2, "是什么": 2, "为什么": 1, "关系": 1, "区别": 1, "概念": 1,
                  "解释": 1, "通俗": 2, "何为": 2, "怎么看": 1, "如何看待": 1, "实例": 1, "入门": 2,
                  "由来": 1, "学习": 1}),
    ("论文解读", {"文献精析": 2, "综述": 2, "预印本": 2, "精读": 2, "research note": 2, "arxiv": 2,
                  "acs nano": 2, "prl": 2, "解读": 1, "解析": 1, "评述": 1, "读后感": 2, "论文": 1,
                  "阅读": 1, "体会": 1}),
]

# ---- 系列识别（按标题关键词，顺序即优先级，可跨主题）----
SERIES_RULES = [
    ("科研绘图系列", ["科研绘图", "作图", "绘图之", "heatmap", "双纵轴", ".fig"]),
    ("文献精读系列", ["文献精析", "精读", "research note", "arxiv", "acs nano", "prl", "解读"]),
    ("理论笔记系列", ["理论笔记"]),
    ("群论系列", ["群论", "群表示", "点群", "空间群", "层群", "晶体点群"]),
    ("Zotero 系列", ["zotero"]),
    ("铁电系列", ["铁电", "ferroelectric", "shift current", "滑移铁电"]),
    ("Skyrmion 系列", ["skyrmion", "斯格明子", "hopfion", "meron"]),
    ("Kagome 系列", ["kagome", "flat band", "van hove"]),
    ("论文写作系列", ["论文写作", "英文学术论文", "写作"]),
]


def classify(it):
    title = (it.get("Title") or "").lower()
    t = title + " " + (it.get("Summary") or "").lower()
    scores = {}
    for name, kws in CAT_RULES:
        s = 0
        for k, w in kws.items():
            if k in t:
                s += w
                if k in title:
                    s += 1
        scores[name] = s
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "其他/随笔"


def series_of(it):
    t = (it.get("Title") or "").lower()
    for name, kws in SERIES_RULES:
        if any(k in t for k in kws):
            return name
    return None


def median(xs):
    return statistics.median(xs) if xs else 0


def stats(sub):
    likes = [i.get("LikeCount") or 0 for i in sub]
    favs = [i.get("FavoriteCount") or 0 for i in sub]
    coms = [i.get("CommentCount") or 0 for i in sub]
    return {
        "n": len(sub),
        "like_sum": sum(likes), "like_mean": round(statistics.mean(likes), 1) if likes else 0,
        "like_median": median(likes),
        "fav_sum": sum(favs), "fav_mean": round(statistics.mean(favs), 1) if favs else 0,
        "fav_median": median(favs),
        "comment_sum": sum(coms), "comment_mean": round(statistics.mean(coms), 1) if coms else 0,
        "fav_like_ratio": round(sum(favs) / sum(likes), 2) if sum(likes) else 0,
    }


def top_rows(items, key, n=10):
    rows = []
    for i in sorted(items, key=lambda x: -(x.get(key) or 0))[:n]:
        rows.append({
            "rank": len(rows) + 1, "title": i.get("Title", ""), "type": i["_type_label"],
            "date": i["_dt"].strftime("%Y-%m"), "like": i.get("LikeCount") or 0,
            "fav": i.get("FavoriteCount") or 0, "comment": i.get("CommentCount") or 0,
            "url": i.get("Url", ""), "cat": i["_cat"], "series": i["_series"],
        })
    return rows


def main():
    items = json.load(open(CACHE, encoding="utf-8"))
    for it in items:
        it["_dt"] = datetime.datetime.fromtimestamp(it.get("CreatedAt") or 0)
        it["_type_label"] = TYPE_LABEL.get(it.get("ContentType"), it.get("ContentType"))
        it["_cat"] = classify(it)
        it["_series"] = series_of(it)

    result = {"fetched_at": json.load(open(os.path.join(ROOT, "data", "fetch_meta.json"), encoding="utf-8")),
              "as_of": TODAY, "total": len(items)}

    # 1. 类型分布
    by_type = Counter(i["ContentType"] for i in items)
    result["type_dist"] = {k: {"count": v, "pct": round(v * 100 / len(items), 1)} for k, v in sorted(by_type.items())}

    # 2. 时间线
    result["year_dist"] = {str(k): v for k, v in sorted(Counter(i["_dt"].year for i in items).items())}
    month_dist = Counter(i["_dt"].strftime("%Y-%m") for i in items)
    result["month_dist"] = {k: month_dist[k] for k in sorted(month_dist)}
    month_type = defaultdict(lambda: defaultdict(int))
    for i in items:
        month_type[i["_dt"].strftime("%Y-%m")][i["ContentType"]] += 1
    result["month_type_dist"] = {k: dict(month_type[k]) for k in sorted(month_type)}
    md_keys = sorted(month_dist)
    result["cadence"] = {
        "active_months": len(month_dist),
        "avg_per_active_month": round(len(items) / len(month_dist), 1),
        "peak_month": max(month_dist, key=month_dist.get),
        "peak_month_count": month_dist[max(month_dist, key=month_dist.get)],
        "span_months": (max(i["_dt"] for i in items) - min(i["_dt"] for i in items)).days // 30,
        "first_year": md_keys[0][:4], "last_year": md_keys[-1][:4],
    }

    # 3. 全局与分类型
    result["global"] = stats(items)
    result["by_type"] = {t: stats([i for i in items if i["ContentType"] == t]) for t in by_type}

    # 4. Top 10
    result["top10_fav"] = top_rows(items, "FavoriteCount")
    result["top10_like"] = top_rows(items, "LikeCount")

    # 5. 主题分类
    by_cat = defaultdict(list)
    for i in items:
        by_cat[i["_cat"]].append(i)
    result["by_cat"] = {k: stats(v) for k, v in sorted(by_cat.items(), key=lambda x: -stats(x[1])["fav_sum"])}

    # 年度收藏贡献（长尾复利分析）
    year_fav = defaultdict(lambda: {"n": 0, "fav_sum": 0, "like_sum": 0})
    for i in items:
        y = str(i["_dt"].year)
        year_fav[y]["n"] += 1
        year_fav[y]["fav_sum"] += i.get("FavoriteCount") or 0
        year_fav[y]["like_sum"] += i.get("LikeCount") or 0
    result["year_fav"] = {k: year_fav[k] for k in sorted(year_fav)}

    # 藏赞比最高内容（干货证据，收藏 ≥ 20 且点赞 ≥ 3）
    ratios = [{"title": i.get("Title", "")[:30], "fav": i.get("FavoriteCount") or 0,
               "like": i.get("LikeCount") or 0,
               "ratio": round((i.get("FavoriteCount") or 0) / max(1, i.get("LikeCount") or 0), 2)}
              for i in items if (i.get("FavoriteCount") or 0) >= 20 and (i.get("LikeCount") or 0) >= 3]
    result["top_ratio"] = sorted(ratios, key=lambda x: -x["ratio"])[:5]

    # 6. 近 90 天 vs 历史
    recent = [i for i in items if i["_dt"] >= NOW - datetime.timedelta(days=90)]
    hist = [i for i in items if i["_dt"] < NOW - datetime.timedelta(days=90)]
    result["recent90"] = stats(recent)
    result["history"] = stats(hist)
    result["recent90_items"] = [{
        "title": i.get("Title", ""), "type": i["_type_label"], "date": i["_dt"].strftime("%Y-%m-%d"),
        "like": i.get("LikeCount") or 0, "fav": i.get("FavoriteCount") or 0, "cat": i["_cat"],
        "series": i["_series"], "fav_day": round((i.get("FavoriteCount") or 0) / max(1, (NOW - i["_dt"]).days), 2),
    } for i in sorted(recent, key=lambda x: -(x.get("FavoriteCount") or 0))]

    # 7. 系列分析（含断更检测）
    by_series = defaultdict(list)
    for i in items:
        if i["_series"]:
            by_series[i["_series"]].append(i)
    series_rows = []
    for name, sub in by_series.items():
        last = max(i["_dt"] for i in sub)
        s = stats(sub)
        series_rows.append({
            "name": name, **s,
            "first": min(i["_dt"] for i in sub).strftime("%Y-%m"),
            "last": last.strftime("%Y-%m"),
            "days_since_last": max(0, (NOW - last).days),
            "top": sorted(sub, key=lambda x: -(x.get("FavoriteCount") or 0))[0].get("Title", ""),
        })
    result["series"] = sorted(series_rows, key=lambda x: -x["fav_sum"])
    result["series_cover"] = {
        "covered": sum(x["n"] for x in series_rows),
        "covered_pct": round(sum(x["n"] for x in series_rows) * 100 / len(items), 1),
    }

    # 8. 收藏速率 / 头部集中度 / 长尾
    items_sorted = sorted(items, key=lambda x: -(x.get("FavoriteCount") or 0))
    top20_n = max(1, round(len(items) * 0.2))
    old_items = [i for i in items if i["_dt"].year <= 2024]
    result["longtail"] = {
        "old_count": len(old_items),
        "old_fav": sum(i.get("FavoriteCount") or 0 for i in old_items),
        "old_fav_share": round(sum(i.get("FavoriteCount") or 0 for i in old_items) / result["global"]["fav_sum"] * 100, 1),
        "top10_old": sum(1 for i in result["top10_fav"] if int(i["date"][:4]) <= 2024),
    }
    result["concentration"] = {
        "top1_share": round(items_sorted[0]["FavoriteCount"] / result["global"]["fav_sum"] * 100, 1),
        "top10_share": round(sum(i.get("FavoriteCount") or 0 for i in items_sorted[:10]) / result["global"]["fav_sum"] * 100, 1),
        "top20pct_share": round(sum(i.get("FavoriteCount") or 0 for i in items_sorted[:top20_n]) / result["global"]["fav_sum"] * 100, 1),
        "top20pct_n": top20_n,
        "zero_items": sum(1 for i in items if (i.get("FavoriteCount") or 0) == 0 and (i.get("LikeCount") or 0) == 0),
    }
    result["rising"] = [{
        "title": i.get("Title", ""), "type": i["_type_label"], "date": i["_dt"].strftime("%Y-%m-%d"),
        "like": i.get("LikeCount") or 0, "fav": i.get("FavoriteCount") or 0,
        "fav_day": round((i.get("FavoriteCount") or 0) / max(1, (NOW - i["_dt"]).days), 2),
        "age_days": max(0, (NOW - i["_dt"]).days),
    } for i in sorted(items, key=lambda x: -(x.get("FavoriteCount") or 0) / max(1, (NOW - x["_dt"]).days))][:8]

    # 9. 星期分布
    wd = defaultdict(list)
    for i in items:
        wd[i["_dt"].weekday()].append(i)
    result["weekday"] = [{
        "weekday": WEEKDAY_CN[d], "n": len(v),
        "fav_mean": round(sum(i.get("FavoriteCount") or 0 for i in v) / len(v), 2),
        "like_mean": round(sum(i.get("LikeCount") or 0 for i in v) / len(v), 2),
    } for d, v in sorted(wd.items())]

    # 10. 标题长度特征
    def tlen(it):
        return len(it.get("Title") or "")
    bins = [(0, 14, "≤14 字"), (15, 24, "15–24 字"), (25, 34, "25–34 字"), (35, 10 ** 6, "≥35 字")]
    result["title_len"] = []
    for lo, hi, label in bins:
        sub = [i for i in items if lo <= tlen(i) <= hi]
        if sub:
            result["title_len"].append({"bin": label, "n": len(sub), **stats(sub)})

    # 11. 历史快照（供跨期趋势）
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    history = []
    if os.path.exists(HISTORY):
        history = json.load(open(HISTORY, encoding="utf-8"))
    if not history or history[-1].get("date") != TODAY:
        snap = {"date": TODAY, "total": len(items),
                "snapshot": {i.get("Url"): {"fav": i.get("FavoriteCount") or 0,
                                            "like": i.get("LikeCount") or 0,
                                            "comment": i.get("CommentCount") or 0,
                                            "created": i.get("CreatedAt")} for i in items}}
        history.append(snap)
        json.dump(history, open(HISTORY, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if len(history) >= 2:
        prev, cur = history[-2], history[-1]
        deltas = []
        for url, cur_v in cur["snapshot"].items():
            prev_v = prev["snapshot"].get(url)
            if prev_v is not None:
                d = {k: cur_v[k] - prev_v[k] for k in ("fav", "like", "comment")}
                if any(d.values()):
                    deltas.append({"url": url, **d})
        result["snapshot_info"] = {"snapshots": len(history),
                                   "first": history[0]["date"], "last": history[-1]["date"],
                                   "delta_items": sorted(deltas, key=lambda x: -x["fav"])[:10]}
    else:
        result["snapshot_info"] = {"snapshots": 1, "first": TODAY, "last": TODAY, "delta_items": []}

    # 12. 内容矩阵（主题 × 类型）
    matrix = {}
    for cat in sorted({i["_cat"] for i in items}):
        matrix[cat] = {}
        for t in by_type:
            sub = [i for i in items if i["_cat"] == cat and i["ContentType"] == t]
            matrix[cat][t] = {"n": len(sub),
                              "fav_mean": round(sum(i.get("FavoriteCount") or 0 for i in sub) / len(sub), 1) if sub else 0,
                              "fav_sum": sum(i.get("FavoriteCount") or 0 for i in sub)}
    result["matrix"] = matrix
    result["matrix_holes"] = [
        {"cat": c, "type": TYPE_LABEL[t], "n": v["n"]}
        for c, row in matrix.items() for t, v in row.items() if v["n"] == 0
    ]

    # 13. 重发/更新清单（高收藏 + 发布超 1 年）
    result["refresh"] = [{
        "title": i.get("Title", ""), "type": i["_type_label"], "date": i["_dt"].strftime("%Y-%m"),
        "like": i.get("LikeCount") or 0, "fav": i.get("FavoriteCount") or 0,
        "age_days": max(0, (NOW - i["_dt"]).days), "series": i["_series"], "cat": i["_cat"],
    } for i in items if (i.get("FavoriteCount") or 0) >= 30 and (NOW - i["_dt"]).days > 365]
    result["refresh"] = sorted(result["refresh"], key=lambda x: -x["fav"])

    # 14. 分层（头部/腰部/长尾）+ 敏感性
    ranked = sorted(items, key=lambda x: -(x.get("FavoriteCount") or 0))
    head, mid, tail = ranked[:10], ranked[10:30], ranked[30:]
    result["tiers"] = {
        "head": {"n": len(head), "label": "头部（Top 10）", "fav_sum": sum(i.get("FavoriteCount") or 0 for i in head),
                 "fav_mean": round(sum(i.get("FavoriteCount") or 0 for i in head) / max(1, len(head)), 1),
                 "like_mean": round(sum(i.get("LikeCount") or 0 for i in head) / max(1, len(head)), 1)},
        "mid": {"n": len(mid), "label": "腰部（11–30 名）", "fav_sum": sum(i.get("FavoriteCount") or 0 for i in mid),
                "fav_mean": round(sum(i.get("FavoriteCount") or 0 for i in mid) / max(1, len(mid)), 1),
                "like_mean": round(sum(i.get("LikeCount") or 0 for i in mid) / max(1, len(mid)), 1)},
        "tail": {"n": len(tail), "label": "长尾（31 名及以后）", "fav_sum": sum(i.get("FavoriteCount") or 0 for i in tail),
                 "fav_mean": round(sum(i.get("FavoriteCount") or 0 for i in tail) / max(1, len(tail)), 1),
                 "like_mean": round(sum(i.get("LikeCount") or 0 for i in tail) / max(1, len(tail)), 1)},
    }
    result["mid_list"] = [{
        "title": i.get("Title", ""), "type": i["_type_label"], "date": i["_dt"].strftime("%Y-%m"),
        "like": i.get("LikeCount") or 0, "fav": i.get("FavoriteCount") or 0, "series": i["_series"],
    } for i in sorted(mid, key=lambda x: -(x.get("FavoriteCount") or 0))[:10]]
    top1 = ranked[0]
    result["sensitivity"] = {
        "without_top1_n": len(items) - 1,
        "fav_mean_without_top1": round((result["global"]["fav_sum"] - (top1.get("FavoriteCount") or 0)) / (len(items) - 1), 2),
        "like_mean_without_top1": round((result["global"]["like_sum"] - (top1.get("LikeCount") or 0)) / (len(items) - 1), 2),
        "top1_share_removed": round((top1.get("FavoriteCount") or 0) / result["global"]["fav_sum"] * 100, 1),
    }

    # 15. 评论互动
    result["comments_top"] = [{
        "title": i.get("Title", ""), "type": i["_type_label"], "date": i["_dt"].strftime("%Y-%m"),
        "like": i.get("LikeCount") or 0, "fav": i.get("FavoriteCount") or 0,
        "comment": i.get("CommentCount") or 0,
    } for i in sorted(items, key=lambda x: -(x.get("CommentCount") or 0))[:10]]
    result["comment_ratio"] = {
        "comment_per_like": round(result["global"]["comment_sum"] / max(1, result["global"]["like_sum"]), 3),
        "comment_per_fav": round(result["global"]["comment_sum"] / max(1, result["global"]["fav_sum"]), 3),
        "by_type": {t: round(v["comment_sum"] / max(1, v["like_sum"]), 3) for t, v in result["by_type"].items()},
    }

    # 16. 标题句式分析
    PAT_RULES = [
        ("疑问句", r"如何|为什么|怎么|有哪些|是什么|能不能|怎样|如何看待|如何理解|哪个|哪款|什么样|需要"),
        ("系列前缀式", r"^(计算工具|文献精析|理论笔记|Research Note|科研论文写作)"),
        ("教程/清单式", r"教程|指南|配置|安装|总结|避坑|清单|使用|接入|笔记|步骤|干货|插件|装上|开源|记录"),
        ("主副标题式", r"：|:"),
    ]
    import re as _re
    def pattern_of(it):
        t = it.get("Title") or ""
        for name, rx in PAT_RULES:
            if _re.search(rx, t):
                return name
        return "陈述式"
    for it in items:
        it["_pat"] = pattern_of(it)
    by_pat = defaultdict(list)
    for i in items:
        by_pat[i["_pat"]].append(i)
    result["title_pattern"] = [{
        "pattern": k, **stats(v),
        "top_examples": [i.get("Title", "") for i in sorted(v, key=lambda x: -(x.get("FavoriteCount") or 0))[:2]],
    } for k, v in sorted(by_pat.items(), key=lambda x: -stats(x[1])["fav_mean"])]

    # 17. CSV 明细导出
    import csv
    csv_path = os.path.join(ROOT, "output", "contents.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["标题", "类型", "发布时间", "赞", "藏", "评论", "主题", "系列", "URL"])
        for i in sorted(items, key=lambda x: x.get("CreatedAt") or 0):
            w.writerow([i.get("Title", ""), i["_type_label"], i["_dt"].strftime("%Y-%m-%d"),
                        i.get("LikeCount") or 0, i.get("FavoriteCount") or 0, i.get("CommentCount") or 0,
                        i["_cat"], i["_series"] or "", i.get("Url", "")])
    result["csv_path"] = "output/contents.csv"

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    g = result["global"]
    print(f"共 {g['n']} 条 | 赞 {g['like_sum']} | 藏 {g['fav_sum']} | 评论 {g['comment_sum']}")
    print("系列:", ", ".join(f"{x['name']} {x['n']}篇/{x['fav_sum']}藏(断更{x['days_since_last']}天)" for x in result["series"][:6]))
    c = result["concentration"]
    print(f"集中度: Top10 占 {c['top10_share']}% | Top20% 占 {c['top20pct_share']}% | 零互动 {c['zero_items']} 条")
    print(f"新锐: {result['rising'][0]['title'][:25]} {result['rising'][0]['fav_day']}藏/天")
    print("历史快照:", result["snapshot_info"]["snapshots"], "份")
    holes = result["matrix_holes"]
    print("矩阵空白格:", holes if holes else "无")
    print(f"重发候选: {len(result['refresh'])} 条 | 腰部 {result['tiers']['mid']['n']} 条 藏均 {result['tiers']['mid']['fav_mean']}"
          f" | 剔除Top1后藏均 {result['sensitivity']['fav_mean_without_top1']}")
    print(f"已写入 {OUT}")


if __name__ == "__main__":
    main()
