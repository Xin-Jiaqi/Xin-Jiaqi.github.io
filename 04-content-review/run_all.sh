#!/bin/bash
# 一键运行：抓取(缓存) → 统计 → 图表 → HTML 报告
set -e
cd "$(dirname "$0")"
python3 src/fetch_contents.py
python3 src/analyze_contents.py
python3 src/report_generator.py
python3 src/make_charts.py
python3 src/build_html.py
echo "完成：output/创作复盘报告.md / .html + charts/"
