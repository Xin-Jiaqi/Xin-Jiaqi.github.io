#!/usr/bin/env python3
"""知乎创作 -> 个人网站片段同步脚本（项目 1 交付物）

数据源：知乎开放平台 zhihu-cli `me contents`（只读，不发布任何内容）
分类：按 zhihu-categories.json 的关键词规则自动归类（默认只匹配标题，避免
      摘要中的背景词干扰；可在配置里打开 summary 匹配），新文章同步后自动
      归入对应主题卡片；规则不足时补充关键词即可。

产出（默认 output/ 目录）：
  - zhihu-section.html  网站可注入的 HTML 片段（按主题分类卡片，含 ZHIHU_SECTION 标记）
  - zhihu-section.md    Markdown 版片段
  - zhihu-data.json     全量结构化数据（含分类，供网站 JS、项目 5 等复用）

用法示例：
  python3 src/sync_zhihu.py                          # 有缓存则用缓存，生成全部产物
  python3 src/sync_zhihu.py --no-cache               # 强制重新抓取
  python3 src/sync_zhihu.py --limit 4                # 每个分类卡片显示 4 条，其余折叠
  python3 src/sync_zhihu.py --categories zhihu-categories.json

CI 场景：ZHIHU_ACCESS_SECRET 环境变量优先于系统凭证库，无需其他配置。
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_CLI = "/Users/jiaqi/Library/Application Support/zhihu-cli/current/zhihu-cli"
TYPE_LABEL = {
    "answer": "回答",
    "article": "文章",
    "pin": "想法",
    "zvideo": "视频",
    "question": "提问",
}
NOTES_START_MARKER = "<!-- ZHIHU_NOTES:START -->"
NOTES_END_MARKER = "<!-- ZHIHU_NOTES:END -->"

# Posts & Notes 融合卡片：知乎分类 -> 站点卡片（顺序即展示顺序；其余分类归入 other 兜底）
NOTES_CARDS = [
    {"key": "theory-notes", "title": "Theory Notes",
     "desc": "群论、层群、凝聚态物理基础和数学物理笔记。",
     "cats": ["symmetry", "theory", "condensed"]},
    {"key": "research-workflow", "title": "Research Workflow",
     "desc": "科研绘图、文献阅读、论文写作和 AI 辅助科研工具。",
     "cats": ["tools", "ai"]},
    {"key": "literature-notes", "title": "Literature Notes",
     "desc": "铁电、斯格明子、激子与位移电流、二维材料与范德华等研究主题的文献阅读笔记。",
     "cats": ["ferroelectrics", "skyrmions", "excitons", "twod"]},
    {"key": "computational-methods", "title": "Computational Methods",
     "desc": "计算材料学概念、能带分析和常用计算方法整理。",
     "cats": ["computational"]},
    {"key": "reading-essays", "title": "Reading & Essays",
     "desc": "阅读、随笔与个人思考。",
     "cats": ["essays"]},
    {"key": "open-source", "title": "Open Source & Projects",
     "desc": "开源项目与个人作品。",
     "cats": ["opensource"]},
    {"key": "others", "title": "Others",
     "desc": "暂未分类的创作。",
     "cats": ["other"]},
]
CACHE_VERSION = 2

# 内置默认分类（无配置文件时兜底；推荐维护 zhihu-categories.json）
DEFAULT_CATEGORIES = [
    {"id": "ferroelectrics", "label": "铁电与极化", "label_en": "Ferroelectricity & Polarization",
     "keywords": ["铁电", "极化", "顺电", "体光伏", "热释电", "磁电"]},
    {"id": "skyrmions", "label": "磁性斯格明子", "label_en": "Skyrmions & Magnetic Textures",
     "keywords": ["skyrmion", "斯格明子", "磁纹理"]},
    {"id": "excitons", "label": "激子与位移电流", "label_en": "Excitons & Shift Current",
     "keywords": ["激子", "exciton", "位移电流"]},
    {"id": "twod", "label": "二维材料与范德华", "label_en": "2D Materials & van der Waals",
     "keywords": ["二维材料", "二维半导体", "范德华", "双层", "monolayer", "bilayer",
                  "mos2", "异质结", "堆叠", "c2db", "ic-2d"]},
    {"id": "computational", "label": "计算方法与软件", "label_en": "Computational Methods",
     "keywords": ["vasp", "poscar", "wannier", "wannsymm", "dft", "materials project", "icsd",
                  "ase", "convex hull", "能带", "紧束缚", "第一性原理", "pymatgen", "spglib", "cif"]},
    {"id": "symmetry", "label": "群论与对称性", "label_en": "Group Theory & Symmetry",
     "keywords": ["群论", "群表示", "表示论", "点群", "空间群", "层群", "对称性", "商群"]},
    {"id": "theory", "label": "数学与理论笔记", "label_en": "Mathematics & Theory Notes",
     "keywords": ["奇异", "线性代数", "范数", "向量", "原子单位", "原子质量", "三体"]},
    {"id": "tools", "label": "科研工具与工作流", "label_en": "Research Tools & Workflow",
     "keywords": ["zotero", "绘图", "matlab", "origin", "pix2tex", "pdfmathtranslate", "论文写作",
                  "写作", "文献", "mole", "翻译", "命令行", "macos", "heatmap", "论文"]},
    {"id": "ai", "label": "AI 与编程实践", "label_en": "AI & Programming",
     "keywords": ["deepseek", "opencode", "llm", "大语言模型", "copilot", "ai 代码", "代码辅助"]},
    {"id": "condensed", "label": "凝聚态基础", "label_en": "Condensed Matter Basics",
     "keywords": ["kagome", "flat band", "平带", "自旋轨道耦合", "轨道耦合", "磁体", "交错磁性"]},
    {"id": "opensource", "label": "开源与个人项目", "label_en": "Open Source & Projects",
     "keywords": ["个人主页", "开源", "模板", "weread-calendar", "moodist"]},
    {"id": "essays", "label": "阅读与随笔", "label_en": "Reading & Essays",
     "keywords": ["复活", "托尔斯泰", "信仰", "灵魂", "读书", "书", "微信读书", "白噪音",
                  "iphone", "edge"]},
    {"id": "other", "label": "其他", "label_en": "Others", "keywords": []},
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="知乎创作 -> 网站片段同步（按主题自动分类）")
    p.add_argument("--cli", default=os.environ.get("ZHIHU_CLI") or DEFAULT_CLI,
                   help="zhihu-cli 可执行文件路径（默认 $ZHIHU_CLI 或本机安装路径）")
    p.add_argument("--categories", help="分类配置文件（JSON，格式见 zhihu-categories.json）")
    p.add_argument("--type", default="all",
                   choices=["all", "answer", "article", "zvideo", "pin", "question"])
    p.add_argument("--sort", default="ts", choices=["ts", "like_count"],
                   help="分类卡片内排序字段")
    p.add_argument("--order", default="desc", choices=["asc", "desc"])
    p.add_argument("--limit", type=int, default=None,
                   help="每个分类卡片默认显示的条数（默认取配置文件 per_category=3）")
    p.add_argument("--cache-dir", default="cache")
    p.add_argument("--ttl-hours", type=float, default=6)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--from-json", help="跳过抓取，直接用已有 zhihu-data.json 渲染产物")
    p.add_argument("--output-dir", default="output")
    p.add_argument("--format", nargs="+", default=["html", "json", "md"],
                   choices=["html", "json", "md"])
    return p.parse_args()


def load_categories(args: argparse.Namespace) -> tuple[list[dict], list[str], int, list[str]]:
    """返回 (分类列表, exclude_types, per_category, match_fields)。配置文件优先，其次内置默认。"""
    cfg = None
    if args.categories:
        path = Path(args.categories)
        if not path.is_file():
            sys.exit(f"[错误] 找不到分类配置文件：{path}")
        cfg = json.loads(path.read_text(encoding="utf-8"))
    else:
        for cand in (Path("zhihu-categories.json"),
                     Path(__file__).resolve().parent.parent / "zhihu-categories.json"):
            if cand.is_file():
                cfg = json.loads(cand.read_text(encoding="utf-8"))
                break
    if cfg is None:
        cats, exclude, per, match = DEFAULT_CATEGORIES, ["pin"], 3, ["title"]
    else:
        cats = cfg.get("categories") or DEFAULT_CATEGORIES
        exclude = cfg.get("exclude_types", ["pin"])
        per = int(cfg.get("per_category", 3))
        match = cfg.get("match_fields", ["title"])
    if not cats or "other" not in {c["id"] for c in cats}:
        cats = [*cats, {"id": "other", "label": "其他", "label_en": "Others", "keywords": []}]
    return cats, exclude, per, match


def classify(text: str, categories: list[dict]) -> str:
    text = text.lower()
    for cat in categories:
        if any(k.lower() in text for k in cat.get("keywords", [])):
            return cat["id"]
    return "other"


def run_cli(cli: str, args: list[str]) -> dict:
    r = subprocess.run([cli, *args], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        sys.exit(f"[错误] zhihu-cli {' '.join(args)} 失败：{r.stderr.strip() or r.stdout.strip()}")
    return json.loads(r.stdout)


def fetch_all(cli: str, content_type: str) -> list[dict]:
    items: list[dict] = []
    offset, total = 0, None
    while True:
        d = run_cli(cli, ["me", "contents", "--type", content_type,
                          "--limit", "50", "--offset", str(offset)])
        data = d.get("Data", {})
        batch = data.get("Items") or []
        items.extend(batch)
        paging = data.get("Paging") or {}
        total = paging.get("Totals", total)
        if not paging.get("IsEnd", True) and paging.get("NextOffset") is not None:
            offset = int(paging["NextOffset"])
        else:
            break
        if total is not None and len(items) >= total:
            break
    return items


def load_or_fetch(args: argparse.Namespace, cli: str) -> tuple[list[dict], bool]:
    cache_dir = Path(args.cache_dir)
    cache_file = cache_dir / f"zhihu_contents_{args.type}.json"
    now = datetime.datetime.now(datetime.timezone.utc)
    if not args.no_cache and cache_file.is_file():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            fetched_at = datetime.datetime.fromisoformat(cached["fetched_at"])
            if cached.get("cache_version") == CACHE_VERSION and \
                    (now - fetched_at).total_seconds() < args.ttl_hours * 3600:
                return cached["items"], True
        except (KeyError, ValueError, json.JSONDecodeError):
            pass
    print(f"[info] 抓取本人创作（type={args.type}）…")
    items = fetch_all(cli, args.type)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(
        {"cache_version": CACHE_VERSION, "fetched_at": now.isoformat(), "items": items},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return items, False


def fmt_date(ts: int | None) -> str:
    if not ts:
        return "—"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def summarize(items: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    likes = favs = comments = 0
    for it in items:
        t = it.get("ContentType") or "unknown"
        by_type[t] = by_type.get(t, 0) + 1
        likes += it.get("LikeCount") or 0
        favs += it.get("FavoriteCount") or 0
        comments += it.get("CommentCount") or 0
    return {"total": len(items), "by_type": by_type,
            "likes": likes, "favorites": favs, "comments": comments}


def note_list_lis(items: list[dict]) -> str:
    lines = []
    for it in items:
        title = html.escape((it.get("Title") or "").strip() or "未命名内容")
        url = html.escape((it.get("Url") or "#").strip(), quote=True)
        lines.append(f'            <li><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></li>')
    return "\n".join(lines)


def render_html(grouped: dict[str, list[dict]], categories: list[dict],
                cat_counts: dict[str, int], summary: dict, args: argparse.Namespace,
                generated_at: datetime.datetime) -> str:
    """渲染为 Posts & Notes 融合片段：一组 note-card 主题卡片。

    - 每个卡片显示最近 --limit 条（默认 per_category=3），其余折叠进 See more
    - 卡片内按创建时间倒序；卡片顺序由 NOTES_CARDS 决定
    - 复用站点现有 .note-card / .post-list / .section-note 样式，无内联样式与脚本
    """
    visible = args.limit if args.limit is not None else 3
    cards = []
    for card in NOTES_CARDS:
        group: list[dict] = []
        for cid in card["cats"]:
            group.extend(grouped.get(cid, []))
        if not group:
            continue
        group.sort(key=lambda x: x.get("CreatedAt") or 0, reverse=True)
        head, rest = group[:visible], group[visible:]
        out = [f'        <div class="note-card">',
               f'          <h3>{card["title"]}</h3>',
               f'          <p class="section-note">{card["desc"]}</p>',
               f'          <ul class="post-list">',
               note_list_lis(head),
               f'          </ul>']
        if rest:
            out.append(f'          <details>')
            out.append(f'            <summary>See more {card["title"].lower()}</summary>')
            out.append(f'            <ul class="post-list">')
            out.append(note_list_lis(rest))
            out.append(f'            </ul>')
            out.append(f'          </details>')
        out.append('        </div>')
        cards.append("\n".join(out))

    by_type = " · ".join(f"{TYPE_LABEL.get(k, k)} {v}" for k, v in sorted(summary["by_type"].items()))
    footer = (f'<p class="section-note" style="grid-column:1/-1">'
              f'由知乎开放平台 Zhihu CLI 自动同步 · 共 {summary["total"]} 条创作'
              f'（{by_type}）· 累计 {summary["likes"]} 赞 / {summary["favorites"]} 藏'
              f' · 更新于 {generated_at.strftime("%Y-%m-%d")}</p>')
    return f"{NOTES_START_MARKER}\n" + "\n\n".join(cards) + "\n" + footer + f"\n{NOTES_END_MARKER}\n"


def render_markdown(items: dict[str, list[dict]], categories: list[dict],
                    cat_counts: dict[str, int], summary: dict, args: argparse.Namespace,
                    generated_at: datetime.datetime) -> str:
    lines = ["## Zhihu Creations（融合进 Posts & Notes）", "",
             f"> 由知乎开放平台 Zhihu CLI 自动同步 · 共 {summary['total']} 条创作"
             f" · 累计 {summary['likes']} 赞 / {summary['favorites']} 藏"
             f" · 更新于 {generated_at.strftime('%Y-%m-%d')}", ""]
    for cat in categories:
        group = sorted(items.get(cat["id"], []),
                       key=lambda x: x.get("CreatedAt") or 0, reverse=True)
        if not group:
            continue
        lines.append(f"### {cat['label']} {cat['label_en']}（{cat_counts.get(cat['id'], 0)} 条）")
        lines.append("")
        for it in group:
            t = it.get("ContentType") or "unknown"
            lines.append(f"- [{it.get('Title', '')}]({it.get('Url', '#')}) · "
                         f"{TYPE_LABEL.get(t, t)} · {fmt_date(it.get('CreatedAt'))} · "
                         f"赞 {it.get('LikeCount') or 0} · 藏 {it.get('FavoriteCount') or 0}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_json(items: list[dict], categories: list[dict], cat_counts: dict[str, int],
                summary: dict, args: argparse.Namespace,
                generated_at: datetime.datetime) -> dict:
    cat_index = {c["id"]: c for c in categories}

    def pick(it: dict) -> dict:
        cid = it.get("_category")
        cat = cat_index.get(cid)
        return {
            "title": it.get("Title", ""),
            "url": it.get("Url", ""),
            "content_type": it.get("ContentType"),
            "created_at": it.get("CreatedAt"),
            "created_date": fmt_date(it.get("CreatedAt")),
            "likes": it.get("LikeCount") or 0,
            "favorites": it.get("FavoriteCount") or 0,
            "comments": it.get("CommentCount") or 0,
            "category": {"id": cid, "label": cat["label"] if cat else cid,
                         "label_en": cat["label_en"] if cat else cid},
            "summary": (it.get("Summary") or "")[:200],
        }

    return {
        "generated_at": generated_at.isoformat(),
        "source": "zhihu-cli me contents",
        "total": summary["total"],
        "summary": summary,
        "categories": [{"id": c["id"], "label": c["label"], "label_en": c["label_en"],
                        "count": cat_counts.get(c["id"], 0)} for c in categories
                       if cat_counts.get(c["id"], 0) > 0],
        "items": [pick(x) for x in items],
    }


def main() -> int:
    args = parse_args()
    cli = os.path.expanduser(args.cli)
    if not Path(cli).is_file():
        sys.exit(f"[错误] 找不到 zhihu-cli：{cli}（可用 --cli 或 $ZHIHU_CLI 指定）")
    categories, exclude_types, per, match_fields = load_categories(args)
    if args.limit is None:
        args.limit = per
    os.makedirs(args.output_dir, exist_ok=True)

    if args.from_json:
        raw = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        items = []
        for x in raw.get("items", []):
            items.append({
                "Title": x.get("title", ""),
                "Url": x.get("url", ""),
                "ContentType": x.get("content_type"),
                "CreatedAt": x.get("created_at"),
                "LikeCount": x.get("likes", 0),
                "FavoriteCount": x.get("favorites", 0),
                "CommentCount": x.get("comments", 0),
                "Summary": x.get("summary", ""),
            })
        from_cache = True
        print(f"[info] 从 {args.from_json} 读取 {len(items)} 条创作")
    else:
        items, from_cache = load_or_fetch(args, cli)
    if not items:
        sys.exit("[错误] 未获取到任何创作数据，请检查 Access Secret 与网络")

    cat_index = {c["id"]: c for c in categories}
    for it in items:
        if it.get("_category"):
            continue
        parts = []
        if "title" in match_fields:
            parts.append(it.get("Title") or "")
        if "summary" in match_fields:
            parts.append(it.get("Summary") or "")
        it["_category"] = classify(" ".join(parts), categories)

    grouped: dict[str, list[dict]] = {c["id"]: [] for c in categories}
    for it in items:
        if it.get("ContentType") in exclude_types:
            continue
        grouped[it["_category"]].append(it)
    cat_counts = {cid: len(grouped[cid]) for cid in grouped}

    summary = summarize(items)
    generated_at = datetime.datetime.now(datetime.timezone.utc)
    print(f"[info] {'缓存' if from_cache else '新抓取'}：{summary['total']} 条创作，"
          f"累计 {summary['likes']} 赞 / {summary['favorites']} 藏")
    for cid, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
        if n:
            print(f"  {cat_index.get(cid, {}).get('label', cid):<16} {n} 条")

    out = Path(args.output_dir)
    if "html" in args.format:
        (out / "zhihu-section.html").write_text(
            render_html(grouped, categories, cat_counts, summary, args, generated_at),
            encoding="utf-8")
        print(f"[ok] {out / 'zhihu-section.html'}")
    if "md" in args.format:
        (out / "zhihu-section.md").write_text(
            render_markdown(grouped, categories, cat_counts, summary, args, generated_at),
            encoding="utf-8")
        print(f"[ok] {out / 'zhihu-section.md'}")
    if "json" in args.format:
        (out / "zhihu-data.json").write_text(
            json.dumps(render_json(items, categories, cat_counts, summary, args, generated_at),
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"[ok] {out / 'zhihu-data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
