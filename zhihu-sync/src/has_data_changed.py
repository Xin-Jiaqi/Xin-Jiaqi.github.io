#!/usr/bin/env python3
"""判断两次同步数据是否有实质变化（忽略 generated_at 时间戳）。

用法：python3 src/has_data_changed.py <旧数据.json> <新数据.json>
退出码：0 = 无实质变化（只有时间戳差异）；1 = 有变化（新内容/赞藏评论变化）。
"""
from __future__ import annotations

import json
import sys


def payload(path: str) -> dict:
    d = json.load(open(path, encoding="utf-8"))
    d.pop("generated_at", None)
    return d


def main() -> int:
    if len(sys.argv) < 3:
        sys.exit("用法：has_data_changed.py <旧文件> <新文件>")
    try:
        old = payload(sys.argv[1])
    except FileNotFoundError:
        return 1  # 旧文件不存在 = 首次运行 = 视为有变化
    new = payload(sys.argv[2])
    return 0 if old == new else 1


if __name__ == "__main__":
    raise SystemExit(main())
