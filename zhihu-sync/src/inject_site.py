#!/usr/bin/env python3
"""把知乎创作片段注入个人网站 index.html 的 Posts & Notes 板块（幂等，基于标记替换）

设计：
  - 片段文件（zhihu-section.html）自带 <!-- ZHIHU_NOTES:START/END --> 标记，
    内容是复用站点 .note-card 样式的主题卡片，直接放进 #notes .note-grid
  - 若 index.html 已有标记：替换标记之间的内容
  - 若没有标记：在 <div class="note-grid"> 之后插入（首次注入会写入标记）
  - 自动清理旧版独立板块的 <!-- ZHIHU_SECTION:... --> 残留
  - 默认 dry-run（只打印差异预览）；--write 才真正修改 --site
  - --output PATH 可把结果写到指定文件（不修改原文件）

用法示例：
  python3 src/inject_site.py --site index.html --fragment output/zhihu-section.html
  python3 src/inject_site.py --site index.html --fragment output/zhihu-section.html --write
  python3 src/inject_site.py --site index.html --fragment output/zhihu-section.html --output output/index.injected.html
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NOTES_START_MARKER = "<!-- ZHIHU_NOTES:START -->"
NOTES_END_MARKER = "<!-- ZHIHU_NOTES:END -->"
LEGACY_START_MARKER = "<!-- ZHIHU_SECTION:START -->"
LEGACY_END_MARKER = "<!-- ZHIHU_SECTION:END -->"
NOTE_GRID_TAG = '<div class="note-grid">'
LEGACY_PATTERN = re.compile(re.escape(LEGACY_START_MARKER) + r".*?" + re.escape(LEGACY_END_MARKER), re.S)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="知乎创作片段注入 index.html")
    p.add_argument("--site", required=True, help="网站 index.html 路径")
    p.add_argument("--fragment", required=True, help="生成的片段文件（zhihu-section.html）")
    p.add_argument("--write", action="store_true", help="真正写回 --site（默认 dry-run）")
    p.add_argument("--output", help="把结果写到指定文件（不与 --write 冲突）")
    return p.parse_args()


def inject(site_text: str, fragment_text: str) -> tuple[str, bool]:
    fragment_text = fragment_text.strip() + "\n"
    site_text = LEGACY_PATTERN.sub("", site_text)
    has_markers = NOTES_START_MARKER in site_text
    if has_markers:
        pattern = re.compile(re.escape(NOTES_START_MARKER) + r".*?" + re.escape(NOTES_END_MARKER), re.S)
        new_text = pattern.sub(fragment_text, site_text, count=1)
        # 归一化：END 标记后最多保留一个换行，保证重复注入幂等
        new_text = re.sub(r"(" + re.escape(NOTES_END_MARKER) + r")\n{2,}", r"\1\n", new_text)
        return new_text, True
    idx = site_text.find(NOTE_GRID_TAG)
    if idx == -1:
        sys.exit("[错误] index.html 中找不到 .note-grid，无法确定插入位置")
    insert_at = idx + len(NOTE_GRID_TAG)
    new_text = site_text[:insert_at] + "\n" + fragment_text + site_text[insert_at:]
    return new_text, False


def main() -> int:
    args = parse_args()
    site = Path(args.site)
    fragment = Path(args.fragment)
    if not site.is_file():
        sys.exit(f"[错误] 找不到 --site：{site}")
    if not fragment.is_file():
        sys.exit(f"[错误] 找不到 --fragment：{fragment}")

    site_text = site.read_text(encoding="utf-8")
    fragment_text = fragment.read_text(encoding="utf-8")
    if NOTES_START_MARKER not in fragment_text or NOTES_END_MARKER not in fragment_text:
        sys.exit("[错误] 片段文件缺少 ZHIHU_NOTES 标记，请用 sync_zhihu.py 重新生成")

    new_text, replaced = inject(site_text, fragment_text)
    delta = len(new_text) - len(site_text)
    print(f"[info] {'替换已有标记区域' if replaced else '首次注入（.note-grid 内插入）'}"
          f" · 大小 {len(site_text)} -> {len(new_text)} ({delta:+d} 字符)")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(new_text, encoding="utf-8")
        print(f"[ok] 结果已写入 {out}（未改动原文件）")
    elif args.write:
        site.write_text(new_text, encoding="utf-8")
        print(f"[ok] 已写入 {site}")
    else:
        print("[dry-run] 未改动任何文件；确认无误后加 --write，或用 --output 输出到新文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
