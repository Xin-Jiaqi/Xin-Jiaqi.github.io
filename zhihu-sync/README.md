# zhihu-sync：知乎创作自动同步

这个目录由知乎 CLI 项目自动维护（详见仓库根目录的同步说明）：

- `src/sync_zhihu.py`：抓取知乎创作 → 自动分类 → 生成 Posts & Notes 融合片段与数据
  （片段是一组 note-card 主题卡片，注入 `index.html` 的 Posts & Notes 板块）
- `src/inject_site.py`：把片段注入 `index.html`（幂等）
- `src/check_uncategorized.py` / `src/has_data_changed.py`：自动化辅助检查
- `tests/validate_zhihu.py`：产物校验
- `zhihu-categories.json`：主题分类规则（新主题在此补充关键词）
- `output/`：每次同步的产物（由 GitHub Actions 自动生成，勿手改）

自动化流程见 `.github/workflows/zhihu-sync.yml`：
每天 06:00 / 18:00（北京时间）自动同步，数据有实质变化时自动更新线上的 Posts & Notes 板块；
出现未分类内容或运行失败时自动创建 Issue 提醒。

本地手动运行：

```bash
python3 zhihu-sync/src/sync_zhihu.py --categories zhihu-sync/zhihu-categories.json
```

### 融合方式

知乎创作不再单独成板块，而是按主题映射为 Posts & Notes 里的卡片（`NOTES_CARDS` 定义）：

| 站点卡片 | 知乎分类 |
|---|---|
| Theory Notes | 群论与对称性 / 数学与理论笔记 / 凝聚态基础 |
| Research Workflow | 科研工具与工作流 / AI 与编程实践 |
| Literature Notes | 铁电与极化 / 磁性斯格明子 / 激子与位移电流 / 二维材料与范德华 |
| Computational Methods | 计算方法与软件 |
| Reading & Essays | 阅读与随笔 |
| Open Source & Projects | 开源与个人项目 |
| Others（兜底，仅在有未分类内容时出现） | 其他 |

每张卡片默认显示最近 3 条（`per_category` / `--limit` 可调），其余折叠进 See more；
想法（pin）按 `exclude_types` 配置不展示。

离线从已有数据重新生成（不调用 CLI）：

```bash
python3 zhihu-sync/src/sync_zhihu.py --from-json zhihu-sync/output/zhihu-data.json \
  --categories zhihu-sync/zhihu-categories.json --output-dir zhihu-sync/output
```
