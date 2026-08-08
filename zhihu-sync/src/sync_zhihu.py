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
START_MARKER = "<!-- ZHIHU_SECTION:START -->"
END_MARKER = "<!-- ZHIHU_SECTION:END -->"
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


def item_li(it: dict) -> str:
    title = html.escape((it.get("Title") or "").strip() or "未命名内容")
    url = html.escape((it.get("Url") or "#").strip(), quote=True)
    t = it.get("ContentType") or "unknown"
    meta = f"{TYPE_LABEL.get(t, t)} · 赞 {it.get('LikeCount') or 0} · 藏 {it.get('FavoriteCount') or 0} · {fmt_date(it.get('CreatedAt'))}"
    return (f'<li data-cat="{html.escape(it.get("_category", "other"), quote=True)}">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
            f'<span class="zhihu-meta">{meta}</span></li>')


def render_html(items: dict[str, list[dict]], categories: list[dict],
                cat_counts: dict[str, int], summary: dict, args: argparse.Namespace,
                generated_at: datetime.datetime) -> str:
    """渲染为单个紧凑卡片：分类标签页 + 搜索框 + 全量列表（无 JS 时全量展示）。

    - 列表按时间倒序渲染全部条目（HTML 静态完整，SEO 友好）
    - JS 增强：点击标签过滤分类；搜索框按标题过滤；无 JS 时列表完整可见
    - 样式使用 .zhihu- 前缀，仅作用于本片段，不影响站点其他区域
    """
    # 全部条目（时间倒序）
    flat = []
    for cat in categories:
        flat.extend(items.get(cat["id"], []))
    flat.sort(key=lambda x: x.get("CreatedAt") or 0, reverse=True)
    lis = "\n".join(f"        {item_li(it)}" for it in flat)

    total_shown = sum(len(v) for v in items.values())
    by_type = " · ".join(f"{TYPE_LABEL.get(k, k)} {v}" for k, v in sorted(summary["by_type"].items()))
    note = (f"由知乎开放平台 Zhihu CLI 自动同步 · 共 {summary['total']} 条创作"
            f"（{by_type}）· 累计 {summary['likes']} 赞 / {summary['favorites']} 藏"
            f" · 更新于 {generated_at.strftime('%Y-%m-%d')}")

    pills = ['<button type="button" class="zhihu-pill active" data-cat="latest">最新 · Latest</button>',
             f'<button type="button" class="zhihu-pill" data-cat="all">全部 · All ({total_shown})</button>']
    for cat in categories:
        n = cat_counts.get(cat["id"], 0)
        if n:
            label = html.escape(cat["label"], quote=True)
            pills.append(f'<button type="button" class="zhihu-pill" data-cat="{cat["id"]}">{label} ({n})</button>')
    pills_html = "\n        ".join(pills)

    style = (
        "<style>\n"
        "  .zhihu-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:2px 0 10px}\n"
        "  .zhihu-pill{padding:5px 13px;border-radius:999px;border:1px solid #d7e6fb;background:rgba(247,250,255,.9);"
        "color:var(--link);font-size:13.5px;line-height:1.5;cursor:pointer;font-family:inherit;transition:all .16s ease}\n"
        "  .zhihu-pill:hover{background:#edf5ff;border-color:#bfd8f7;transform:translateY(-1px)}\n"
        "  .zhihu-pill.active{background:var(--link);border-color:var(--link);color:#fff}\n"
        "  .zhihu-search{width:100%;padding:8px 13px;border:1px solid #e1e7f0;border-radius:12px;"
        "background:#fbfcff;color:var(--text);font-size:14px;font-family:inherit;margin-bottom:10px;box-sizing:border-box}\n"
        "  .zhihu-search:focus{outline:none;border-color:#bfd8f7;background:#fff}\n"
        "  .zhihu-list{margin:0;padding:0;list-style:none}\n"
        "  .zhihu-list li{padding:7px 0;border-bottom:1px dashed #eceef2;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}\n"
        "  .zhihu-list li:last-child{border-bottom:none}\n"
        "  .zhihu-list a{color:var(--text);text-decoration:none;font-size:15px;line-height:1.5;flex:1 1 260px;min-width:0}\n"
        "  .zhihu-list a:hover{color:var(--link)}\n"
        "  .zhihu-meta{color:var(--muted);font-size:12.5px;white-space:nowrap}\n"
        "  .zhihu-count{color:var(--muted);font-size:13px;margin:8px 2px 0;text-align:right}\n"
        "  @media (max-width:600px){.zhihu-meta{white-space:normal}}\n"
        "</style>"
    )
    script = (
        "<script>\n"
        "(function(){var list=document.getElementById('zhihu-list');if(!list)return;"
        "var items=Array.prototype.slice.call(list.children);"
        "var pills=Array.prototype.slice.call(document.querySelectorAll('#zhihu .zhihu-pill'));"
        "var search=document.getElementById('zhihu-search');"
        "var count=document.getElementById('zhihu-count');"
        "var state={cat:'latest',q:''};"
        "function apply(){var q=state.q.toLowerCase(),shown=0,latest=0;"
        "items.forEach(function(li){var c=li.getAttribute('data-cat');"
        "var inCat=state.cat==='all'||c===state.cat;"
        "if(state.cat==='latest'){inCat=latest<10;latest++;}"
        "if(q){inCat=li.textContent.toLowerCase().indexOf(q)>-1;}"
        "li.style.display=inCat?'':'none';if(inCat)shown++;});"
        "count.textContent='显示 '+shown+' / '+items.length+' 条';}"
        "pills.forEach(function(p){p.addEventListener('click',function(){"
        "pills.forEach(function(x){x.classList.toggle('active',x===p)});"
        "state.cat=p.getAttribute('data-cat');apply();});});"
        "if(search){search.addEventListener('input',function(){state.q=search.value;apply();});}"
        "apply();})();\n"
        "</script>"
    )
    body = (
        f'<section class="card" id="zhihu">\n'
        f'    <h2>Zhihu Creations · 知乎创作</h2>\n'
        f'    <p class="section-note">{note}</p>\n'
        f'    {style}\n'
        f'    <div class="zhihu-tabs" role="tablist" aria-label="知乎创作分类">\n'
        f'        {pills_html}\n'
        f'    </div>\n'
        f'    <input id="zhihu-search" class="zhihu-search" type="search" '
        f'placeholder="搜索知乎创作（标题关键词）…" aria-label="搜索知乎创作">\n'
        f'    <ul class="zhihu-list" id="zhihu-list">\n'
        f'        {lis}\n'
        f'    </ul>\n'
        f'    <p class="zhihu-count" id="zhihu-count">共 {total_shown} 条 · 点击上方分类标签筛选</p>\n'
        f'    <noscript><p class="zhihu-count">已完整展示全部 {total_shown} 条创作</p></noscript>\n'
        f'    {script}\n'
        f'  </section>'
    )
    return f"{START_MARKER}\n{body}\n{END_MARKER}\n"



def render_markdown(items: dict[str, list[dict]], categories: list[dict],
                    cat_counts: dict[str, int], summary: dict, args: argparse.Namespace,
                    generated_at: datetime.datetime) -> str:
    lines = ["## Zhihu Creations · 知乎创作", "",
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

    items, from_cache = load_or_fetch(args, cli)
    if not items:
        sys.exit("[错误] 未获取到任何创作数据，请检查 Access Secret 与网络")

    cat_index = {c["id"]: c for c in categories}
    for it in items:
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
