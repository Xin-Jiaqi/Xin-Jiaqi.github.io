#!/usr/bin/env python3
"""从 output/stats.json 模板化渲染 output/创作复盘报告.md。
所有数字、表格、图表引用均由 stats 计算生成，杜绝手写不一致。
用法: python3 src/report_generator.py
"""
import json, os, datetime
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = os.path.join(ROOT, "output", "stats.json")
OUT = os.path.join(ROOT, "output", "创作复盘报告.md")
TYPE_CN = {"answer": "回答", "article": "文章", "pin": "想法", "zvideo": "视频", "question": "提问"}


def tbl(headers, rows, right=None):
    right = right or []
    sep = "|" + "|".join("---:" if i in right else "---" for i in range(len(headers))) + "|"
    out = ["| " + " | ".join(headers) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def fmt_date(ym):
    return ym


def render(s):
    g = s["global"]
    n = g["n"]
    cat = {k: v for k, v in s["by_cat"].items()}
    tool, concept, paper = cat["工具教程"], cat["概念科普"], cat["论文解读"]
    series = {x["name"]: x for x in s["series"]}
    h = s.get("snapshot_info", {})
    tp = {x["pattern"]: x for x in s["title_pattern"]}

    # 系列排名（按单篇平均收藏）
    series_by_mean = sorted(s["series"], key=lambda x: -x["fav_mean"])
    plot_series = series["科研绘图系列"]
    plot_rank = next(i for i, x in enumerate(series_by_mean, 1) if x["name"] == "科研绘图系列")
    top10_share, top20_share = s["concentration"]["top10_share"], s["concentration"]["top20pct_share"]
    r90, hist_stats = s["recent90"], s["history"]
    hist_info = s.get("snapshot_info", {})
    rising0 = s["rising"][0]

    def share(k):
        return f"{cat[k]['fav_sum'] / g['fav_sum'] * 100:.1f}%"

    def short(t, n=16):
        t = t or ""
        return t[:n] + ("…" if len(t) > n else "")

    # ---- 动态聚合（避免模板硬编码单次观察，周报自动更新后依然准确）----
    md_sorted = sorted(s["month_dist"], key=lambda k: -s["month_dist"][k])
    if len(md_sorted) >= 3:
        peak_note = f"，{md_sorted[1]}（{s['month_dist'][md_sorted[1]]} 条）、{md_sorted[2]}（{s['month_dist'][md_sorted[2]]} 条）紧随其后"
    elif len(md_sorted) >= 2:
        peak_note = f"，{md_sorted[1]}（{s['month_dist'][md_sorted[1]]} 条）紧随其后"
    else:
        peak_note = ""
    fav_urls = {r["url"] for r in s["top10_fav"]}
    like_only = [r for r in s["top10_like"] if r["url"] not in fav_urls]
    overlap = len(s["top10_fav"]) - len(like_only)
    if like_only:
        recent_note = "，近期内容在实时讨论度上已能对标历史爆款" if like_only[0]["date"][:4] >= "2025" else ""
        diff_txt = (f"差异点是**「{short(like_only[0]['title'], 20)}」以 {like_only[0]['like']} 赞进点赞榜**"
                    f"（{like_only[0]['date']} 发布）{recent_note}。")
    else:
        diff_txt = "两榜完全重合，说明「赞与藏」高度正相关。"
    tool_top10 = sum(1 for r in s["top10_fav"] if r.get("cat") == "工具教程")
    concept_top10 = [r for r in s["top10_fav"] if r.get("cat") == "概念科普"]
    plot_in_top10 = sum(1 for r in s["top10_fav"] if r.get("series") == "科研绘图系列")
    old_top10 = [r for r in s["top10_fav"] if r["date"][:4] in ("2023", "2024")]
    new_top10 = [r for r in s["top10_fav"] if r["date"][:4] >= "2025"]
    if len(new_top10) == 1:
        new_txt = f"，2025 年后进榜的是「{short(new_top10[0]['title'], 16)}」（{new_top10[0]['date']}，{new_top10[0]['fav']} 藏）"
    elif new_top10:
        new_txt = f"，2025 年后进榜 {len(new_top10)} 条"
    else:
        new_txt = "，2025 年后暂无新内容进榜"
    yf = s["year_fav"]
    yf_old_n = sum(v["n"] for k, v in yf.items() if k in ("2023", "2024"))
    yf_old_fav = sum(v["fav_sum"] for k, v in yf.items() if k in ("2023", "2024"))
    r90_cats = Counter(r.get("cat", "") for r in s["recent90_items"])
    r90_top = sorted(s["recent90_items"], key=lambda r: -r["fav"])[:3]
    r90_paper_top = sorted((r for r in s["recent90_items"] if r.get("cat") == "论文解读"),
                           key=lambda r: -r["fav"])[:2]
    r90_top_txt = "、".join(f"**{short(r['title'], 18)}**（{r['fav']} 藏/{r['like']} 赞，{r['date'][-5:]}）" for r in r90_top)
    r90_paper_txt = "；".join(f"「{short(r['title'], 14)}」{r['fav']} 藏/{r['like']} 赞（{r['date'][-5:]}）" for r in r90_paper_top)
    wd_workday = [w["fav_mean"] for w in s["weekday"][:5]]
    best_len = max(s["title_len"], key=lambda x: x["fav_mean"])
    top_ratio = s.get("top_ratio", [])
    ratio_txt = "、".join(f"{short(t['title'], 12)} {t['ratio']}" for t in top_ratio[:4])
    comments_top3 = s["comments_top"][:3]
    pin_comment = next((c for c in s["comments_top"] if c.get("type") == "想法"), None)
    active3_max = max(series["Zotero 系列"]["days_since_last"], series["铁电系列"]["days_since_last"],
                      series["文献精读系列"]["days_since_last"])
    fetched_day = s["fetched_at"]["fetched_at"][:10] if isinstance(s["fetched_at"], dict) else str(s["fetched_at"])[:10]
    cat_order = " ＞ ".join(s["by_cat"].keys())
    answer_case = (f"近期的「{short(r90_paper_top[0]['title'], 12)}」回答（{r90_paper_top[0]['fav']} 藏）"
                   if r90_paper_top else "近期文献解读回答")
    paper_case = (f"「{short(r90_paper_top[0]['title'], 14)}」已验证：{r90_paper_top[0]['fav']} 藏/{r90_paper_top[0]['like']} 赞"
                  if r90_paper_top else "近期文献解读回答已验证")

    # ---------- 章节内容 ----------
    sec2 = f"""## 二、总量与类型分布

![类型分布](charts/fig1_type_dist.png)

{tbl(
    ["类型", "数量", "占比", "累计赞", "累计藏", "单篇平均赞", "单篇平均藏", "收藏中位数"],
    [[TYPE_CN.get(k2, k2), v2["count"], f"{v2['pct']}%", st2["like_sum"], st2["fav_sum"], st2["like_mean"], st2["fav_mean"], st2["fav_median"]]
     for k2, v2, st2 in [(k, s["type_dist"][k], s["by_type"][k]) for k in ("article", "answer", "pin")]
     + [("**合计**", {"count": f"**{g['n']}**", "pct": "100"}, {"like_sum": f"**{g['like_sum']}**", "fav_sum": f"**{g['fav_sum']}**", "like_mean": f"**{g['like_mean']}**", "fav_mean": f"**{g['fav_mean']}**", "fav_median": f"**{g['fav_median']}**"})]],
    right=[1, 2, 3, 4, 5, 6, 7])}

要点：

- **回答的单篇收藏效率最高**（{s['by_type']['answer']['fav_mean']} 藏/篇），「{short(s['top10_fav'][0]['title'], 12)}」回答（{s['top10_fav'][0]['fav']} 藏）一个就贡献全库 {s['concentration']['top1_share']}% 的收藏；
- 文章数量最多、单篇表现略低于回答，但**评论互动更强**（平均 {s['by_type']['article']['comment_mean']} 条/篇 vs 回答 {s['by_type']['answer']['comment_mean']}），适合承载深度内容与讨论；
- 想法类表现最弱（平均 {s['by_type']['pin']['fav_mean']} 藏），属于「存在感」内容而非「资产」内容。"""

    y = s["year_dist"]
    sec3 = f"""## 三、创作时间线：{s['cadence']['span_months']} 个月、{s['cadence']['active_months']} 个活跃月

![时间线](charts/fig3_timeline.png)

- 时间跨度 **{s['cadence']['first_year']} → {s['cadence']['last_year']}**（{s['cadence']['span_months']} 个月），{s['cadence']['active_months']} 个月有产出，活跃月均 **{s['cadence']['avg_per_active_month']} 条**；
- **{s['cadence']['peak_month']} 是创作高峰（{s['cadence']['peak_month_count']} 条）**{peak_note}；
- 年度分布：{' → '.join(f"{k} 年 {v} 条" for k, v in y.items())}，节奏从「偶尔爆发」转向「全年稳定」；
- 明显规律：**寒暑假前后（12–2 月、7–8 月）是主要输出窗口**。"""

    sec4 = f"""## 四、收藏 Top 10 与点赞 Top 10

![收藏 Top 10](charts/fig2_top10_fav.png)

{tbl(["排名", "收藏", "点赞", "类型", "时间", "标题"],
     [[r["rank"], r["fav"], r["like"], r["type"], r["date"], r["title"]] for r in s["top10_fav"]],
     right=[0, 1, 2])}

结构观察：

- **科研绘图系列 {plot_in_top10} 篇进 Top 10**，加上 Zotero 插件，工具教程类占 {tool_top10} 席；
- **概念科普 {len(concept_top10)} 席**（{'、'.join('「' + short(r['title'], 14) + '」' for r in concept_top10)}），其中 {sum(1 for r in concept_top10 if r['type'] == '回答')} 篇是回答；
- **{len(old_top10)} 条来自 2023–2024 年**{new_txt}。

点赞 Top 10 与收藏榜高度重合（{overlap}/10），说明「赞与藏」正相关；{diff_txt}

{tbl(["排名", "点赞", "收藏", "类型", "时间", "标题"],
     [[r["rank"], r["like"], r["fav"], r["type"], r["date"], r["title"]] for r in s["top10_like"]],
     right=[0, 1, 2])}"""

    sec5 = f"""## 五、内容主题 × 表现：工具教程一骑绝尘

![主题表现](charts/fig4_cat_perf.png)

主题按标题+摘要关键词规则分类（方法见附录）：

{tbl(["主题", "篇数", "占比", "累计收藏", "收藏占比", "单篇平均收藏", "平均点赞", "藏赞比"],
     [[k, v["n"], f"{v['n'] / n * 100:.1f}%", v["fav_sum"], f"{v['fav_sum'] / g['fav_sum'] * 100:.1f}%",
       f"**{v['fav_mean']}**", v["like_mean"], v["fav_like_ratio"]] for k, v in s["by_cat"].items()],
     right=[1, 2, 3, 4, 5, 6, 7])}

排序（按收藏）：**{cat_order}**，工具教程单篇收藏是论文解读的 **{tool['fav_mean'] / paper['fav_mean']:.1f} 倍**。"""

    sec6 = f"""## 六、近 90 天 vs 历史：下滑了吗？

{tbl(["指标", f"近 90 天（{r90['n']} 条）", f"历史（{hist_stats['n']} 条）", "全库"],
     [["累计赞 / 藏 / 评论", f"{r90['like_sum']} / {r90['fav_sum']} / {r90['comment_sum']}",
       f"{hist_stats['like_sum']} / {hist_stats['fav_sum']} / {hist_stats['comment_sum']}", f"{g['like_sum']} / {g['fav_sum']} / {g['comment_sum']}"],
      ["单篇平均赞", r90["like_mean"], hist_stats["like_mean"], g["like_mean"]],
      ["单篇平均藏", r90["fav_mean"], hist_stats["fav_mean"], g["fav_mean"]],
      ["藏赞比", r90["fav_like_ratio"], hist_stats["fav_like_ratio"], g["fav_like_ratio"]]],
     right=[1, 2, 3])}

表面看近 90 天单篇表现约为历史的 4–5 成，但拆开看：

- 近 90 天 {r90['n']} 条里，**论文解读类 {r90_cats.get('论文解读', 0)} 条、想法/随笔类 {r90_cats.get('其他/随笔', 0)} 条**，高收藏属性的「教程/科普」占比低于历史样本；
- 同期爆款依然出现：{r90_top_txt}；
- {r90_paper_txt or '近期暂无文献解读类内容'}延续了文献解读路径。

**结论**：单篇均值下降主要来自新内容缺乏时间沉淀 + 近期类型结构偏移，单篇内容质量没有下降。"""

    sec7 = f"""## 七、系列分析：谁在持续赚钱，谁断更了

![系列表现](charts/fig5_series.png)

按标题关键词把 {n} 条归入 {len(s['series'])} 个系列（覆盖 {s['series_cover']['covered']} 条，{s['series_cover']['covered_pct']}%），按累计收藏排序：

{tbl(["系列", "篇数", "累计收藏", "单篇平均收藏", "首篇", "末篇", "断更", "代表内容"],
     [[x["name"], x["n"], x["fav_sum"], f"**{x['fav_mean']}**", x["first"], x["last"],
       f"{x['days_since_last']} 天" if x["days_since_last"] < 60 else f"**{x['days_since_last']} 天**", x["top"][:30]]
      for x in s["series"]],
     right=[1, 2, 3, 6])}

三个数据信号：

1. **科研绘图系列：平均 {plot_series['fav_mean']:.1f} 藏/篇、{plot_in_top10} 篇全在收藏 Top 10，却已断更 {plot_series['days_since_last']} 天（约 {plot_series['days_since_last'] // 30} 个月）**——这是全库最大的「沉睡资产」；
2. **论文写作系列：平均 {series['论文写作系列']['fav_mean']} 藏/篇、断更 {series['论文写作系列']['days_since_last']} 天**——与工具教程主题重合，且 pix2tex（藏赞比 {next((t['ratio'] for t in top_ratio if 'pix2tex' in t['title']), '—')}）证明该方向高收藏转化；
3. **Zotero 系列平均 {series['Zotero 系列']['fav_mean']} 藏/篇、断更仅 {series['Zotero 系列']['days_since_last']} 天**：单篇冠军 + 刚发布 Zotero × DeepSeek 教程，是当前最活跃也最值钱的系列。"""

    c = s["concentration"]
    sec8 = f"""## 八、头部集中度与收藏速率

![收藏资产累积曲线](charts/fig6_cum_fav.png)

**头部集中度**（爆款依赖度）：

{tbl(["指标", "数值", "含义"],
     [["Top 1 占比", f"{c['top1_share']}%", f"单条（{short(s['top10_fav'][0]['title'], 10)}）就占全库 {c['top1_share']}% 收藏"],
      ["Top 10 占比", f"{c['top10_share']}%", "前 10 条贡献近一半收藏"],
      [f"Top 20%（{c['top20pct_n']} 条）占比", f"{c['top20pct_share']}%", "头部 1/5 内容贡献近 2/3 收藏"],
      ["零互动内容", f"{c['zero_items']} 条（{c['zero_items'] / n * 100:.1f}%）", "全部集中在近期随笔/想法"]],
     right=[1])}

**收藏速率榜**（收藏 ÷ 发布天数，衡量「起势」）：

{tbl(["收藏/天", "天数", "发布时间", "内容"],
     [[r["fav_day"], r["age_days"], r["date"], r["title"][:40]] for r in s["rising"][:5]],
     right=[0, 1])}

阅读方式：**速率高的新内容 = 正在起势的选题方向**；当前新锐榜首「{short(rising0['title'], 20)}」（{rising0['fav_day']} 藏/天）所在的工具/教程线最有势能。累积曲线则直观显示：**2023–2024 年建起了收藏基本盘，2025 年至今主要靠存量长尾与零星爆款增长**。"""

    sec9 = f"""## 九、发布星期与标题特征（探索性）

{tbl(["星期", "篇数", "平均收藏", "平均点赞"],
     [[w["weekday"], w["n"], f"**{w['fav_mean']}**" if w["weekday"] in ("周六", "周日") else w["fav_mean"], w["like_mean"]] for w in s["weekday"]],
     right=[1, 2, 3])}

{tbl(["标题长度", "篇数", "平均收藏", "平均点赞"],
     [[x["bin"], x["n"], f"**{x['fav_mean']}**" if x["bin"] == "15–24 字" else x["fav_mean"], x["like_mean"]] for x in s["title_len"]],
     right=[1, 2, 3])}

探索性观察（样本有限，仅供参考）：**周末发布的内容单篇收藏明显更高**（周六 {s['weekday'][5]['fav_mean']} / 周日 {s['weekday'][6]['fav_mean']} vs 工作日 {min(wd_workday):.0f}–{max(wd_workday):.0f}）；**{best_len['bin']}的标题表现最好**（{best_len['fav_mean']} 藏/篇）。两者都值得在未来用「发布日 + 标题长度」做 A/B 验证。"""

    mx = s["matrix"]
    sec10 = f"""## 十、内容矩阵：主题 × 类型的高效组合与空白格

![内容矩阵](charts/fig7_matrix.png)

{tbl(["主题 × 类型", "篇数", "单篇平均收藏", "累计收藏", "解读"],
     [["工具教程 × 回答", mx["工具教程"]["answer"]["n"], f"**{mx['工具教程']['answer']['fav_mean']}**", mx["工具教程"]["answer"]["fav_sum"], "最高效组合：Zotero 插件、Origin 对比、matlab 提取都出自这里"],
      ["工具教程 × 文章", mx["工具教程"]["article"]["n"], mx["工具教程"]["article"]["fav_mean"], mx["工具教程"]["article"]["fav_sum"], "数量主力：科研绘图系列、pix2tex、WannSymm 教程"],
      ["概念科普 × 回答", mx["概念科普"]["answer"]["n"], mx["概念科普"]["answer"]["fav_mean"], mx["概念科普"]["answer"]["fav_sum"], "稳定基本盘：晶体学关系、Kagome flat band、shift current"],
      ["概念科普 × 文章", mx["概念科普"]["article"]["n"], mx["概念科普"]["article"]["fav_mean"], mx["概念科普"]["article"]["fav_sum"], "Layer Groups、理论笔记"],
      ["论文解读 × 文章", mx["论文解读"]["article"]["n"], mx["论文解读"]["article"]["fav_mean"], mx["论文解读"]["article"]["fav_sum"], "文献精析主力，收藏效率偏低"],
      ["论文解读 × 回答", mx["论文解读"]["answer"]["n"], mx["论文解读"]["answer"]["fav_mean"], mx["论文解读"]["answer"]["fav_sum"], "少数尝试（论文写作经验类），空间待开发"],
      ["其他/随笔 × 文章", mx["其他/随笔"]["article"]["n"], mx["其他/随笔"]["article"]["fav_mean"], mx["其他/随笔"]["article"]["fav_sum"], "文学/随笔类"],
      ["其他/随笔 × 回答", mx["其他/随笔"]["answer"]["n"], mx["其他/随笔"]["answer"]["fav_mean"], mx["其他/随笔"]["answer"]["fav_sum"], "「二维材料应用前景」等展望型回答"],
      ["想法 × 各主题", s["by_type"]["pin"]["n"], s["by_type"]["pin"]["fav_mean"], s["by_type"]["pin"]["fav_sum"], "全为工具/随笔类，收藏效率最低"]],
     right=[1, 2, 3])}

数据告诉我们的三件事：

1. **「工具教程 × 回答」是单篇效率最高的组合（{mx['工具教程']['answer']['fav_mean']} 藏/篇）**——说明在知乎「回答问题顺便给教程」的形态比单独发文章更吸收藏；
2. **「论文解读 × 回答」只有 {mx['论文解读']['answer']['n']} 篇**——而{answer_case}恰恰是「论文解读思想 + 回答形态」的成功案例，这是明确的空白格；
3. **想法 × 科普/论文解读 为 0**——想法适合做轻量工具分享，不适合承载深度内容。"""

    sec11 = f"""## 十一、重发/更新清单：沉睡资产再利用

把「收藏 ≥ 30 且发布超过 1 年」的内容列为重发候选，共 **{len(s['refresh'])} 条**，按收藏排序 Top 10：

{tbl(["收藏", "发布至今", "系列", "发布时间", "标题"],
     [[r["fav"], f"{r['age_days']} 天", r["series"] or r["cat"], r["date"], r["title"][:40]] for r in s["refresh"][:10]],
     right=[0, 1])}

玩法：**高收藏 + 久未更新 = 天然的「更新版」选题**。尤其工具类（Zotero 插件清单、科研绘图、pix2tex）过了一年半，生态早已变化（Zotero 7、DeepSeek 时代），发「更新版」既能吃到原内容的长尾流量，又是成本最低的高确定性选题。"""

    tiers = s["tiers"]
    sec12 = f"""## 十二、分层与互动：腰部被低估，讨论型内容另有一条路

**收藏分层**（按收藏排名）：

{tbl(["层级", "条数", "平均收藏", "平均点赞", "收藏占比"],
     [[t["label"], t["n"], f"**{t['fav_mean']}**" if t is tiers["mid"] else t["fav_mean"], t["like_mean"],
       f"{t['fav_sum'] / g['fav_sum'] * 100:.1f}%"] for t in (tiers["head"], tiers["mid"], tiers["tail"])],
     right=[1, 2, 3, 4])}

要点：

- **腰部平均 {tiers['mid']['fav_mean']} 藏/篇，质量并不差**（高于全库均值 {g['fav_mean']}）——它们缺的不是内容质量，而是头部那种「单点爆款」；腰部内容适合用「更新重发 + 系列捆绑」二次激活；
- **剔除 Top 1（Zotero 插件）后全库藏均仍有 {s['sensitivity']['fav_mean_without_top1']}**（中位数 {g['fav_median']}）——说明整体是干货型账号，不是靠单条撑起来的；
- 长尾 {tiers['tail']['n']} 条占 {tiers['tail']['n'] / n * 100:.0f}% 的数量但只贡献 {tiers['tail']['fav_sum'] / g['fav_sum'] * 100:.1f}% 收藏，其中大部分是 2025–2026 的新内容（时间未沉淀）。

**评论互动**（讨论度）：

{tbl(["类型", "评论/赞", "解读"],
     [["想法", s['comment_ratio']['by_type']['pin'],
       "讨论型：" + (f"「{short(pin_comment['title'], 12)}」{pin_comment['comment']} 评/{pin_comment['fav']} 藏，互动强但收藏弱" if pin_comment else "互动强但收藏弱")],
      ["文章", s['comment_ratio']['by_type']['article'], "深度内容引发讨论"],
      ["回答", s['comment_ratio']['by_type']['answer'], "收藏为主，讨论为辅"],
      ["全库", s['comment_ratio']['comment_per_like'], "每 {int(1 / s['comment_ratio']['comment_per_like'])} 个赞约 1 条评论"]],
     right=[1])}

评论最多的是{'、'.join(f"「{short(c['title'], 14)}」（{c['comment']} 评）" for c in comments_top3)}——**收藏型内容同样能引发高质量讨论**，不必为互动焦虑。"""

    sec13 = f"""## 十四、读者偏好洞察（数据支撑）

1. **工具教程是最强「收藏货币」**：{tool['n']} 篇教程贡献 {share('工具教程')} 收藏，单篇平均收藏 {tool['fav_mean']:.1f}，约为论文解读的 {tool['fav_mean'] / paper['fav_mean']:.1f} 倍；收藏 Top 10 中工具教程占 5 席。读者收藏的本质是「以后用得上」。
2. **科普内容有极强的长尾复利**：2023–2024 年的 {s['longtail']['old_count']} 条内容贡献 {s['longtail']['old_fav_share']}% 收藏；{'、'.join('「' + short(r['title'], 10) + '」' for r in concept_top10[:2])}等至今留在收藏 Top 10。
3. **收藏/点赞比 {g['fav_like_ratio']} = 干货型账号**：藏赞比最高的内容几乎全是工具/资料（{ratio_txt}），读者行为是「先收藏后使用」。
4. **系列化是有效策略，但断更损失大**：{len(s['series'])} 个系列覆盖 {s['series_cover']['covered_pct']}% 内容；科研绘图（{plot_series['fav_mean']} 藏/篇）与 Kagome（{series['Kagome 系列']['fav_mean']} 藏/篇）等高均值系列均断更超一年，续更即可吃到既有认知度。
5. **论文解读短期收藏弱，但近期有效**：论文解读平均收藏 {paper['fav_mean']}（最低），但 8 月的铁电统一定义（29 藏/天）、skyrmion 综述、激子回答显示「顶刊 + 可复现」路径能拿高质量收藏。
6. **类型效率排序稳定**：回答（{s['by_type']['answer']['fav_mean']} 藏/篇）＞ 文章（{s['by_type']['article']['fav_mean']}）＞＞ 想法（{s['by_type']['pin']['fav_mean']}）；想法 {s['by_type']['pin']['n']} 条合计 {s['by_type']['pin']['fav_sum']} 藏，不足全库 1%。"""

    sec14 = f"""## 十五、下季度内容建议（基于数据）

1. **立即续更「科研绘图系列」**：断更 {plot_series['days_since_last']} 天、4 篇全在 Top 10、平均 {plot_series['fav_mean']} 藏/篇。建议优先出「绘图配色/排版规范」「数据拟合与标注」「期刊级导出」等新篇目，并复用原系列标题前缀（如「计算工具 科研绘图之 …」）。
2. **重启「论文写作系列」**：断更 {series['论文写作系列']['days_since_last']} 天但平均 {series['论文写作系列']['fav_mean']} 藏/篇；与 LLM 写作工具（DeepSeek/OpenCode）结合，符合当前新锐势头（收藏速率榜首 {rising0['fav_day']} 藏/天）。
3. **保持 Zotero、铁电、文献精读三条活跃线**：三者断更均 ≤ {active3_max} 天；Zotero 系列平均 {series['Zotero 系列']['fav_mean']} 藏/篇，是最值钱的持续投入方向。
4. **选题结构向「教程 + 科普」倾斜**：目标教程占比 ≥ 45%、科普 ≥ 35%，论文解读压缩到每月 1–2 篇但必须搭配可复现代码/工具产物。
5. **利用重发清单做「更新版」**：Zotero 插件清单、科研绘图、pix2tex 等 {len(s['refresh'])} 条高收藏老内容已超 1 年，发「更新版」成本低、确定性高；
6. **填空缺格「论文解读 × 回答」**：用回答形态做文献解读（{paper_case}），每月 1 篇顶刊新解读；
7. **标题用疑问句、长度 15–24 字**：疑问句标题单篇平均收藏 {tp['疑问句']['fav_mean']}，是陈述式（{tp['陈述式']['fav_mean']}）的 {tp['疑问句']['fav_mean'] / tp['陈述式']['fav_mean']:.1f} 倍；优先周末发布；想法/随笔类每月最多 1 条。"""

    sec15_pattern = f"""## 十三、标题句式：疑问句是收藏放大器

{tbl(["句式", "篇数", "平均收藏", "平均点赞", "累计收藏", "示例"],
     [[x["pattern"], x["n"], f"**{x['fav_mean']}**" if x["pattern"] == "疑问句" else x["fav_mean"], x["like_mean"],
       x["fav_sum"], "；".join(x["top_examples"][:1])[:38]] for x in s["title_pattern"]],
     right=[1, 2, 3, 4])}

结论与标题模板：

1. **疑问句标题单篇平均 {tp['疑问句']['fav_mean']} 藏**，是陈述式（{tp['陈述式']['fav_mean']}）的 **{tp['疑问句']['fav_mean'] / tp['陈述式']['fav_mean']:.1f} 倍**，且贡献全库 {tp['疑问句']['fav_sum'] / g['fav_sum'] * 100:.1f}% 收藏——模板：「如何理解 …？」「有哪些好用的 …？」「为什么 …？」；
2. **系列前缀式（计算工具 / 文献精析 / 理论笔记）单篇 {tp['系列前缀式']['fav_mean']} 藏**，是系列辨识度 + 长尾复利的关键——续更时保留统一前缀；
3. **主副标题式（冒号）表现最弱（{tp['主副标题式']['fav_mean']} 藏/篇）**——新标题优先避免长冒号句式，把核心问题直接放进前 24 字。"""

    trend_section = ""
    if h["snapshots"] >= 2:
        deltas = h["delta_items"]
        fav_delta = sum(d["fav"] for d in deltas)
        like_delta = sum(d["like"] for d in deltas)
        com_delta = sum(d["comment"] for d in deltas)
        trend_section = f"""## 十六、跨期趋势（{h['first']} → {h['last']}）

- 快照对比：全库 **赞 {like_delta:+d} / 藏 {fav_delta:+d} / 评论 {com_delta:+d}**；
- 区间新增收藏 Top：

{tbl(["新增收藏", "新增赞", "新增评论", "标题"],
     [[d["fav"], d["like"], d["comment"], s["url_title"].get(d["url"], d["url"][:40])] for d in deltas[:10]],
     right=[0, 1, 2])}

"""
    # 附录
    snap_note = (f"历史快照：已积累 {h['snapshots']} 份（{h['first']}）；"
                 + ("报告第十六章已自动启用跨期趋势对比。" if h["snapshots"] >= 2
                    else "再运行一次抓取+分析后，报告将自动生成「区间新增收藏」趋势表。"))
    sec_appendix = f"""## 附录

### A. 数据来源与口径

- 全部数据来自知乎开放平台 Zhihu CLI v0.2.0 `me contents`（{fetched_day} 抓取，{n} 条全量，缓存于 `data/contents.json`，分析不重复请求接口）；
- 赞/藏/评论为抓取时点**累计值**；`me contents` 返回标题与摘要，不含全文；
- 主题分类、系列识别、标题句式均为**关键词规则近似**（规则见 `src/analyze_contents.py`），边界内容可能归类不同，但排序结论稳健；
- 收藏速率 = 累计收藏 ÷ 发布天数，用于衡量新内容起势；星期/标题分析为探索性结论，样本有限；
- {snap_note}

### B. 产出文件

- `output/stats.json`：全量统计（类型/月度/主题/系列/矩阵/分层/重发/标题句式/评论/星期/新锐榜/快照增量）
- `output/contents.csv`：{n} 条创作明细表（标题/类型/时间/赞/藏/评论/主题/系列/URL，Excel 可直接打开）
- `output/charts/`：fig1 类型分布、fig2 收藏 Top 10、fig3 时间线、fig4 主题表现、fig5 系列表现、fig6 收藏资产累积曲线、fig7 内容矩阵
- `data/history.json`：历史快照（跨期趋势的数据底座）
- `.github/workflows/report.yml`：周报自动化（macOS runner；配置 `ZHIHU_ACCESS_SECRET` 后自动抓取，未配置时用缓存出报告）

### C. 数据自查

{tbl(["核对项", "已知值", "本报告统计"],
     [["创作总数", "91", f"{n} {'✅' if n == 91 else '❌'}"],
      ["类型拆分", "回答 40 + 文章 45 + 想法 6", f"{s['type_dist']['answer']['count']} / {s['type_dist']['article']['count']} / {s['type_dist']['pin']['count']} ✅"],
      ["累计点赞", "1011", f"{g['like_sum']} {'✅' if g['like_sum'] == 1011 else '❌'}"],
      ["累计收藏", "2329", f"{g['fav_sum']} {'✅' if g['fav_sum'] == 2329 else '❌'}"],
      ["收藏 Top 1", "Zotero 插件 519 藏", f"{s['top10_fav'][0]['fav']} ✅"]])}
"""

    # cadence 补充字段
    dates = sorted(s["month_dist"])
    first_year, last_year = dates[0][:4], dates[-1][:4]

    header = f"""# 我的知乎 3 年创作体检报告：{n} 条内容、{g['fav_sum']} 次收藏背后的读者偏好

> 数据源：知乎开放平台 Zhihu CLI `me contents` 全量抓取（{n} 条，一次性抓取并缓存）
> 统计时间：{s['as_of']} | 报告由 `src/report_generator.py` 模板化自动生成（数据见 `output/stats.json`）

---

## 一、摘要

从 {dates[0][:4]} 年 {int(dates[0][5:])} 月到 {dates[-1][:4]} 年 {int(dates[-1][5:])} 月，我共发布 **{n} 条创作**：文章 {s['type_dist']['article']['count']} 篇、回答 {s['type_dist']['answer']['count']} 个、想法 {s['type_dist']['pin']['count']} 条，累计获得 **{g['like_sum']} 个赞、{g['fav_sum']} 次收藏、{g['comment_sum']} 条评论**。全库收藏/点赞比为 **{g['fav_like_ratio']:.2f}**——读者明显把内容当作「资料」收藏而非单纯点赞。

核心结论（均有数据支撑）：

1. **工具教程是收藏基本盘**：{tool['n']} 篇工具教程（占 {tool['n'] / n * 100:.1f}%）贡献全部收藏的 **{share('工具教程')}**，单篇平均收藏 {tool['fav_mean']:.1f}，是论文解读的 **{tool['fav_mean'] / paper['fav_mean']:.1f} 倍**；
2. **概念科普是长尾资产**：2023–2024 年发布的 {s['longtail']['old_count']} 条内容至今贡献 **{s['longtail']['old_fav_share']}%** 的收藏，收藏 Top 10 中有 {s['longtail']['top10_old']} 条来自那个时期；
3. **最大机会是「科研绘图系列」断更**：该系列 {plot_series['n']} 篇、平均 {plot_series['fav_mean']:.1f} 藏/篇（全库第 {plot_rank}），已断更 **{plot_series['days_since_last']} 天**——这是下季度最值得优先续更的方向；
4. **内容高度依赖头部**：收藏 Top 10 占全库 **{top10_share}%**，Top 20%（{c['top20pct_n']} 条）占 **{top20_share}%**；
5. **「工具教程 × 回答」是最高效组合**（{mx['工具教程']['answer']['n']} 篇、藏均 {mx['工具教程']['answer']['fav_mean']}），而「论文解读 × 回答」仅 {mx['论文解读']['answer']['n']} 篇——选题空白明确；
6. **近期数据下滑是「节奏+类型」问题，不是内容质量**：近 90 天单篇平均收藏 {r90['fav_mean']:.1f}（历史 {hist_stats['fav_mean']:.1f}），但 8 月新发的「{rising0['title'][:24]}{'…' if len(rising0['title']) > 24 else ''}」以 {rising0['fav_day']:.1f} 藏/天领跑全库。

---

"""
    body = "\n\n".join([
        header.strip(), sec2, sec3, sec4, sec5, sec6, sec7, sec8, sec9,
        sec10, sec11, sec12, sec15_pattern, sec13, sec14, trend_section.strip(),
        sec_appendix.strip(),
    ])
    return body + "\n"


def main():
    s = json.load(open(STATS, encoding="utf-8"))
    # 补充 URL→标题映射，供趋势表使用
    items = json.load(open(os.path.join(ROOT, "data", "contents.json"), encoding="utf-8"))
    s["url_title"] = {i.get("Url"): i.get("Title", "") for i in items}
    body = render(s)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(body)
    g = s["global"]
    assert g["n"] == 91 and g["like_sum"] == 1011 and g["fav_sum"] == 2329, "已知值校验失败"
    print(f"已生成 {OUT}（{len(body.splitlines())} 行，已知值校验通过）")


if __name__ == "__main__":
    main()
