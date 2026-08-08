# 项目 4：创作复盘报告（04-content-review）

基于知乎开放平台 Zhihu CLI 的 `me contents` 全量数据，自动生成「创作体检报告」：类型分布、时间趋势、累计/单篇表现、Top N、系列分析、读者偏好洞察，输出 Markdown + 自包含 HTML 报告（附图表）。

## 目录结构

```
04-content-review/
├── README.md                 # 本文件
├── run_all.sh                # 一键运行：抓取 → 统计 → 图表 → HTML
├── .github/workflows/
│   └── report.yml            # 可选周报自动化（需用户确认 + 配置 Secret）
├── src/
│   ├── fetch_contents.py     # 抓取本人全量创作并缓存（分页，最多 2 次接口调用）
│   ├── analyze_contents.py   # 统计：类型/时间线/Top N/主题/系列/矩阵/分层/重发/标题句式/快照
│   ├── report_generator.py   # 模板化渲染 Markdown 报告（数字全部来自 stats.json，防手改不一致）
│   ├── make_charts.py        # 生成 7+1 张中文图表（matplotlib，PNG 300dpi）
│   └── build_html.py         # Markdown 报告 → 自包含 HTML（图表 base64 内嵌）
├── data/
│   ├── contents.json         # 91 条创作原始缓存（勿提交凭证）
│   ├── fetch_meta.json       # 抓取元信息（时间、总数）
│   └── history.json          # 历史快照（每次分析自动追加；≥2 份后报告输出区间增量）
└── output/
    ├── 创作复盘报告.md        # 完整报告（可直接发知乎/网站）
    ├── 创作复盘报告.html      # 自包含网页版（本地打开/放个人网站）
    ├── contents.csv          # 91 条创作明细（Excel 可直接打开）
    ├── stats.json            # 全量统计 JSON（报告的数据底座）
    └── charts/
        ├── fig1_type_dist.png    # 类型分布
        ├── fig2_top10_fav.png    # 收藏 Top 10
        ├── fig3_timeline.png     # 月度创作时间线
        ├── fig4_cat_perf.png     # 主题 × 平均收藏
        ├── fig5_series.png       # 系列 × 平均收藏（含断更标注）
        ├── fig6_cum_fav.png      # 收藏资产累积曲线
        └── fig7_matrix.png       # 内容矩阵（主题 × 类型）热力图
```

## 运行方式

前置条件：本机已配置 zhihu-cli Access Secret（参考 `shared/zhihu-cli-notes.md`）。

```bash
# 一键运行（推荐）
./run_all.sh

# 或分步执行
python3 src/fetch_contents.py          # 抓取（已缓存则复用，--force 强制重抓）
python3 src/analyze_contents.py        # 统计 → output/stats.json + data/history.json
python3 src/report_generator.py        # 模板化渲染 → output/创作复盘报告.md（含已知值自检）
python3 src/make_charts.py             # 图表 → output/charts/
python3 src/build_html.py              # HTML 报告 → output/创作复盘报告.html
```

依赖：Python 3.8+、matplotlib（macOS 自动选用 PingFang/Hiragino；Linux 可改用 Noto Sans CJK）。

## 报告结构（Markdown 与 HTML 同源）

1. 摘要（5 条核心结论）
2. 总量与类型分布（图 1）
3. 创作时间线（图 3）
4. 收藏 Top 10 / 点赞 Top 10（图 2）
5. 内容主题 × 表现（图 4）
6. 近 90 天 vs 历史对比
7. **系列分析**：系列篇数/收藏/断更检测，自动找出「沉睡系列」（图 5）
8. **头部集中度与收藏速率**：Top N 占比、新锐内容榜（图 6）
9. **发布星期与标题特征**（探索性）
10. **内容矩阵**：主题 × 类型篇数与效率，找选题空白格（图 7）
11. **重发/更新清单**：高收藏 + 发布超 1 年的内容 → 「更新版」选题（18 条）
12. **分层与互动**：头部/腰部/长尾 + 剔除 Top1 敏感性 + 评论分析
13. **标题句式**：疑问句/系列前缀/冒号式等 × 收藏表现，给出标题模板
14. 读者偏好洞察（6 条，全部带数据）
15. 下季度内容建议（7 条，含矩阵空白格与重发清单）
16. **跨期趋势**（快照 ≥ 2 份后自动出现）：区间新增收藏 Top（图 8）
17. 附录（数据口径、产出文件、自查表）

## 新增能力（本次迭代）

- **系列分析**：按标题关键词把内容归入 9 个系列（科研绘图/理论笔记/群论/Zotero/铁电等），统计每系列表现与断更天数 → 报告自动给出续更优先级（如「科研绘图系列断更 892 天，最值得优先续更」）
- **收藏速率与集中度**：收藏 ÷ 发布天数识别「新锐起势内容」；Top 1 / Top 10 / Top 20% 占比衡量爆款依赖度
- **星期与标题特征**：星期 × 表现、标题长度 × 表现（探索性结论）
- **内容矩阵**：主题 × 类型交叉表，自动标出空白格（如「论文解读 × 回答」仅 3 篇 → 选题建议）
- **重发/更新清单**：收藏 ≥ 30 且发布超 1 年的 18 条内容，直接作为「更新版」选题池
- **分层与敏感性**：头部/腰部/长尾三层表现；剔除 Top1 后藏均 20.1，证明非单点撑起
- **评论互动**：讨论型（想法）vs 收藏型（回答）内容画像
- **报告生成器**：`report_generator.py` 从 stats.json 模板化渲染，所有数字自动计算，跑完自带已知值断言（91/1011/2329），杜绝手改不一致
- **标题句式**：疑问句（38.9 藏/篇）是陈述式（10.2）的 3.8 倍，冒号式最弱（6.6）——直接给出可复用的标题模板
- **CSV 明细**：`output/contents.csv`，Excel 可直接筛选分析
- **周报自动化**：`.github/workflows/report.yml` 每周自动跑并提交报告（需用户确认后启用）
- **历史快照**：每次分析把当次累计值存入 `data/history.json`；≥ 2 次抓取后报告将自动生成「区间新增收藏」趋势表
- **HTML 自包含报告**：图表以 base64 内嵌，单文件 540KB 左右，可直接本地打开或放入个人网站

## 关键数字（与已知值核对一致）

- 91 条 = 回答 40 + 文章 45 + 想法 6
- 累计 1011 赞 / 2329 藏 / 97 评论
- 收藏 Top 1：Zotero 插件（519 藏）；科研绘图系列 4 篇进 Top 10
- 主题排序（按收藏）：工具教程（58.1%）＞ 概念科普（30.9%）＞ 论文解读（6.8%）
- 集中度：Top 10 占 49.4%，Top 20%（18 条）占 64.3%

## GitHub Actions 自动化

`.github/workflows/report.yml`：每周一北京时间 09:00 自动抓取 → 统计 → 图表 → HTML，
有变化时提交临时分支并自动 PR 合并（符合网站仓库 protect-main 规则）。

- 已配置 `ZHIHU_ACCESS_SECRET`：官方 manifest 安装 zhihu-cli（大小 + SHA-256 校验）并抓取最新创作；
- 未配置 Secret：自动降级用仓库内 `data/` 缓存生成报告，全链路不中断；
- 运行失败：自动创建 Issue 附日志链接，异常才人工介入。

部署方式：把 `src/ data/ output/ README.md` 放到网站仓库 `04-content-review/` 目录，
把 `.github/workflows/report.yml` 放到仓库根 `.github/workflows/report.yml`。

## 约束说明

- 所有数据只读，凭证不落盘（抓取走本机已配置的 zhihu-cli）；
- 脚本带缓存，分析类任务不重复请求接口；
- 主题分类/系列识别为关键词近似，边界内容可能归类不同，但排序结论稳健；
- 发知乎时需手动上传 `output/charts/*.png` 并替换 Markdown 图片链接（CLI 只读，无法自动发布）；HTML 版无需处理，直接可用。
