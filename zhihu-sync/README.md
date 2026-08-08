# zhihu-sync：知乎创作自动同步

这个目录由知乎 CLI 项目自动维护（详见仓库根目录的同步说明）：

- `src/sync_zhihu.py`：抓取知乎创作 → 自动分类 → 生成网站片段与数据
- `src/inject_site.py`：把片段注入 `index.html`（幂等）
- `src/check_uncategorized.py` / `src/has_data_changed.py`：自动化辅助检查
- `tests/validate_zhihu.py`：产物校验
- `zhihu-categories.json`：主题分类规则（新主题在此补充关键词）
- `output/`：每次同步的产物（由 GitHub Actions 自动生成，勿手改）

自动化流程见 `.github/workflows/zhihu-sync.yml`：
每天 06:00 / 18:00（北京时间）自动同步，数据有实质变化时自动更新线上页面；
出现未分类内容或运行失败时自动创建 Issue 提醒。

本地手动运行：

```bash
python3 zhihu-sync/src/sync_zhihu.py --categories zhihu-sync/zhihu-categories.json
```
