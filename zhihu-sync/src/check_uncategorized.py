#!/usr/bin/env python3
"""检查未分类创作，供 workflow 自动提醒（异常才人工）。

用法：python3 src/check_uncategorized.py <zhihu-data.json>
输出：第一行 = 未分类条数；后续行 = 每条标题（最多 8 条）。
无未分类时输出 0。
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "zhihu-data.json"
    data = json.load(open(path, encoding="utf-8"))
    items = [i for i in data.get("items", []) if i.get("category", {}).get("id") == "other"]
    print(len(items))
    for it in items[:8]:
        print(f"- {it.get('title', '')[:60]}（{it.get('content_type', '')}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
