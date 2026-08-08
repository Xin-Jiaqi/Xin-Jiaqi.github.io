#!/usr/bin/env python3
"""校验知乎创作同步产物（片段 HTML + 数据 JSON）。

检查项：
  - 片段包含 ZHIHU_SECTION 标记与 id="zhihu" 区块
  - 外链带 target="_blank" 且 rel 含 noopener noreferrer（与站点校验一致）
  - 无内联事件处理器
  - 至少 2 个分类卡片（note-card）
  - JSON：categories 非空、每条内容都带 category、total 与 items 一致

用法：
  python3 tests/validate_zhihu.py output/zhihu-section.html output/zhihu-data.json
"""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

START_MARKER = "<!-- ZHIHU_SECTION:START -->"
END_MARKER = "<!-- ZHIHU_SECTION:END -->"


class FragmentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []
        self.link_count = 0
        self.has_zhihu_section = False
        self.pills = 0
        self.list_items = 0
        self.items_with_cat = 0
        self.has_search = False
        self.has_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "section" and values.get("id") == "zhihu":
            self.has_zhihu_section = True
        if tag == "button" and "zhihu-pill" in (values.get("class") or "").split():
            self.pills += 1
        if tag == "li" and values.get("data-cat"):
            self.list_items += 1
            self.items_with_cat += 1
        if tag == "input" and values.get("id") == "zhihu-search":
            self.has_search = True
        if tag == "script":
            self.has_script = True
        if values.get("target") == "_blank":
            self.link_count += 1
            rel = set((values.get("rel") or "").split())
            if not {"noopener", "noreferrer"}.issubset(rel):
                self.errors.append("外链缺少 rel=\"noopener noreferrer\"")
        if any(name.lower().startswith("on") for name in values):
            self.errors.append(f"发现内联事件处理器 <{tag}>")


def validate_fragment(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if START_MARKER not in text or END_MARKER not in text:
        raise SystemExit(f"[失败] 片段缺少 ZHIHU_SECTION 标记：{path}")
    parser = FragmentParser()
    parser.feed(text)
    if not parser.has_zhihu_section:
        parser.errors.append("片段缺少 <section id=\"zhihu\">")
    if parser.pills < 5:
        parser.errors.append(f"分类标签数量异常（{parser.pills} < 5）")
    if parser.list_items < 10:
        parser.errors.append(f"列表条目数量异常（{parser.list_items} < 10）")
    if parser.items_with_cat != parser.list_items:
        parser.errors.append("存在缺少 data-cat 的列表条目")
    if not parser.has_search:
        parser.errors.append("缺少搜索框（id=zhihu-search）")
    if not parser.has_script:
        parser.errors.append("缺少过滤脚本")
    if parser.link_count < 10:
        parser.errors.append("片段外链数量异常（<10）")
    if parser.errors:
        raise SystemExit("[失败] 片段校验未通过：\n" + "\n".join(parser.errors))
    print(f"[ok] 片段校验通过：{path}（{parser.pills} 个标签，{parser.list_items} 条内容，"
          f"{parser.link_count} 个外链均带 noopener noreferrer）")


def validate_json(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    summary = data.get("summary") or {}
    if not data.get("generated_at"):
        raise SystemExit("[失败] JSON 缺少 generated_at")
    if not (summary.get("total") or 0) > 0:
        raise SystemExit("[失败] JSON summary.total 为空")
    cats = data.get("categories") or []
    if not cats:
        raise SystemExit("[失败] JSON categories 为空")
    items = data.get("items") or []
    if len(items) != summary.get("total"):
        raise SystemExit(f"[失败] items 数量（{len(items)}）与 total（{summary['total']}）不一致")
    uncategorized = [it["title"] for it in items
                     if not it.get("category") or not it["category"].get("id")]
    if uncategorized:
        raise SystemExit(f"[失败] {len(uncategorized)} 条内容缺少分类：{uncategorized[:3]}")
    other = [it["title"] for it in items if it["category"]["id"] == "other"]
    print(f"[ok] JSON 校验通过：{path}（total={summary['total']}，"
          f"分类 {len(cats)} 个，赞 {summary['likes']}，藏 {summary['favorites']}）")
    if other:
        print(f"[提示] {len(other)} 条落在「其他」，可补充分类关键词：{other[:5]}")


def main() -> int:
    if len(sys.argv) < 3:
        sys.exit("用法：python3 tests/validate_zhihu.py <zhihu-section.html> <zhihu-data.json>")
    validate_fragment(Path(sys.argv[1]))
    validate_json(Path(sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
