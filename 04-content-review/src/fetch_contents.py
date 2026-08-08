#!/usr/bin/env python3
"""抓取本人全部创作并缓存为本地 JSON（供分析使用，避免反复消耗配额）。
用法: python3 src/fetch_contents.py [--force] [--cli PATH]
输出: data/contents.json + data/fetch_meta.json

CLI 路径优先级：--cli 参数 > ZHIHU_CLI_PATH 环境变量 > 本机默认路径。
无可用 CLI 或调用失败时自动降级为缓存数据（CI 首次运行、未配置 Secret 也能出报告）。
"""
import json, os, subprocess, sys, datetime, argparse

DEFAULT_CLI = os.environ.get(
    "ZHIHU_CLI_PATH",
    "/Users/jiaqi/Library/Application Support/zhihu-cli/current/zhihu-cli",
)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CACHE = os.path.join(DATA_DIR, "contents.json")
META = os.path.join(DATA_DIR, "fetch_meta.json")


def run(cli, cmd):
    r = subprocess.run([cli] + cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout)


def fetch_all(cli):
    items, offset, total = [], 0, None
    while True:
        d = run(cli, ["me", "contents", "--type", "all", "--limit", "50", "--offset", str(offset)])
        data = d["Data"]
        batch = data["Items"]
        items += batch
        total = data["Paging"]["Totals"]
        if not data["Paging"].get("IsEnd", True):
            offset = int(data["Paging"]["NextOffset"])
        else:
            break
        if len(items) >= total:
            break
    return items, total


def use_cache(reason=""):
    with open(CACHE, encoding="utf-8") as f:
        cached = json.load(f)
    prefix = f"警告: {reason}，降级使用缓存" if reason else "使用缓存"
    print(f"{prefix}: {CACHE}（{len(cached)} 条，加 --force 重新抓取）")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="忽略缓存，强制重新抓取")
    ap.add_argument("--cli", default=DEFAULT_CLI, help="zhihu-cli 可执行文件路径")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    if not args.force and os.path.exists(CACHE):
        use_cache()
        return

    if not os.path.exists(args.cli):
        if os.path.exists(CACHE):
            use_cache(f"未找到 zhihu-cli（{args.cli}）")
            return
        sys.exit(
            f"错误: 找不到 zhihu-cli（{args.cli}），且无缓存可用。"
            "请通过 --cli 参数或 ZHIHU_CLI_PATH 环境变量指定路径"
        )

    try:
        items, total = fetch_all(args.cli)
    except (RuntimeError, OSError) as e:
        if os.path.exists(CACHE):
            use_cache(f"CLI 调用失败（{e}）")
            return
        sys.exit(f"错误: CLI 调用失败（{e}），且无缓存可用")

    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    meta = {"fetched_at": datetime.datetime.now().isoformat(), "total": total, "count": len(items)}
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"抓取完成: {len(items)} 条（Totals={total}），已缓存到 {CACHE}")


if __name__ == "__main__":
    main()
