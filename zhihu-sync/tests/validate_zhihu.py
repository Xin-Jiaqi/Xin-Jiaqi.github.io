#!/usr/bin/env python3
"""校验知乎创作同步产物（融合片段 HTML + 数据 JSON）。

检查项：
  - 片段包含 ZHIHU_NOTES 标记，且不含旧版独立板块（id="zhihu"）
  - 至少 4 个 note-card 主题卡片
  - 外链带 target="_blank" 且 rel 含 noopener noreferrer（与站点校验一致）
  - 无内联事件处理器
  - JSON：categories 非空、每条内容都带 category、total 与 items 一致

用法：
  python3 tests/validate_zhihu.py output/zhihu-section.html output/zhihu-data.json
"""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

NOTES_START_MARKER = "<!-- ZHIHU_NOTES:START -->"
NOTES_END_MARKER = "<!-- ZHIHU_NOTES:END -->"


class FragmentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []
        self.link_count = 0
        self.note_cards = 0
        self.list_items = 0
        self.has_legacy_section = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "section" and values.get("id") == "zhihu":
            self.has_legacy_section = True
        if tag == "div" and "note-card" in (values.get("class") or "").split():
            self.note_cards += 1
        if tag == "li":
            self.list_items += 1
        if values.get("target") == "_blank":
            self.link_count += 1
            rel = set((values.get("rel") or "").split())
            if not {"noopener", "noreferrer"}.issubset(rel):
                self.errors.append("外链缺少 rel=\"noopener noreferrer\"")
        if any(name.lower().startswith("on") for name in values):
            self.errors.append(f"发现内联事件处理器 <{tag}>")


def validate_fragment(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if NOTES_START_MARKER not in text or NOTES_END_MARKER not in text:
        raise SystemExit(f"[失败] 片段缺少 ZHIHU_NOTES 标记：{path}")
    if "<!-- ZHIHU_SECTION:START -->" in text:
        raise SystemExit("[失败] 片段仍包含旧版 ZHIHU_SECTION 标记，请重新生成")
    parser = FragmentParser()
    parser.feed(text)
    if parser.has_legacy_section:
        parser.errors.append("片段仍包含旧版 <section id=\"zhihu\"> 独立板块")
    if parser.note_cards < 4:
        parser.errors.append(f"note-card 主题卡片数量异常（{parser.note_cards} < 4）")
    if parser.list_items < 10:
        parser.errors.append(f"列表条目数量异常（{parser.list_items} < 10）")
    if parser.errors:
        raise SystemExit("[失败] 片段校验不通过：\n" + "\n".join(parser.errors))
    print(f"[ok] 片段有效：{parser.note_cards} 个卡片 / {parser.list_items} 条 / {parser.link_count} 个外链")


def validate_json(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not data.get("categories"):
        raise SystemExit("[失败] JSON categories 为空")
    if data.get("total") != len(items):
        raise SystemExit(f"[失败] JSON total={data.get('total')} 与 items={len(items)} 不一致")
    for it in items:
        cat = (it.get("category") or {}).get("id")
        if not cat:
            raise SystemExit(f"[失败] 存在缺少 category 的内容：{it.get('title', '')[:40]}")
    print(f"[ok] JSON 有效：total={data.get('total')} / categories={len(data['categories'])}")


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("用法：python3 tests/validate_zhihu.py <zhihu-section.html> <zhihu-data.json>")
    fragment_path, json_path = Path(sys.argv[1]), Path(sys.argv[2])
    validate_fragment(fragment_path)
    validate_json(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
