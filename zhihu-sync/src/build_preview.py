#!/usr/bin/env python3
"""生成 zhihu-preview.html：用站点真实 CSS 包裹片段，供本地预览。

用法：
  python3 src/build_preview.py [--site index.html] [--fragment output/zhihu-section.html] [--output output/zhihu-preview.html]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="生成片段独立预览页")
    p.add_argument("--site", default="work/Xin-Jiaqi.github.io/index.html")
    p.add_argument("--fragment", default="output/zhihu-section.html")
    p.add_argument("--output", default="output/zhihu-preview.html")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    site = Path(args.site)
    fragment = Path(args.fragment)
    if not site.is_file():
        sys.exit(f"[错误] 找不到 --site：{site}")
    if not fragment.is_file():
        sys.exit(f"[错误] 找不到 --fragment：{fragment}")

    css_match = re.search(r"<style>.*?</style>", site.read_text(encoding="utf-8"), re.S)
    if not css_match:
        sys.exit("[错误] 站点文件中找不到 <style>")
    frag = fragment.read_text(encoding="utf-8")
    frag = re.sub(r"<!-- ZHIHU_(SECTION|NOTES):START -->\s*|\s*<!-- ZHIHU_(SECTION|NOTES):END -->", "", frag).strip()

    doc = ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
           "<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
           "<title>Posts & Notes 融合片段预览</title>\n"
           f"{css_match.group(0)}\n"
           "</head>\n<body>\n"
           "<div class=\"container\" style=\"padding-top:28px\">\n"
           f"{frag}\n"
           "</div>\n</body>\n</html>\n")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"[ok] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
