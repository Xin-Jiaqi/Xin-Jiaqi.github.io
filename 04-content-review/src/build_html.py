#!/usr/bin/env python3
"""把 output/创作复盘报告.md 转换为自包含 HTML（图表以 base64 内嵌），
输出 output/创作复盘报告.html，可直接本地打开或放到个人网站栏目。
用法: python3 src/build_html.py
"""
import base64, html, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, "output", "创作复盘报告.md")
OUT = os.path.join(ROOT, "output", "创作复盘报告.html")

CSS = """
body{max-width:820px;margin:0 auto;padding:32px 20px 64px;font-family:-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;color:#1f2328;line-height:1.75}
h1{font-size:1.7em;border-bottom:3px solid #056de8;padding-bottom:10px}
h2{font-size:1.3em;margin-top:2em;border-left:4px solid #056de8;padding-left:10px}
h3{font-size:1.1em}
blockquote{color:#57606a;border-left:4px solid #d0d7de;margin:1em 0;padding:4px 14px;background:#f6f8fa}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:.92em}
th,td{border:1px solid #d0d7de;padding:6px 10px;text-align:left}
th{background:#f6f8fa;font-weight:600}
tr:nth-child(even) td{background:#fafbfc}
img{max-width:100%;border:1px solid #eaeef2;border-radius:8px;margin:10px 0}
hr{border:none;border-top:1px solid #d0d7de;margin:2em 0}
code{background:#f6f8fa;border-radius:4px;padding:2px 5px;font-size:.9em}
a{color:#0969da;text-decoration:none}
"""


def inline(s, base):
    def repl_img(m):
        alt, path = m.group(1), m.group(2)
        full = os.path.join(base, path) if not os.path.isabs(path) else path
        try:
            b64 = base64.b64encode(open(full, "rb").read()).decode()
        except OSError:
            return f'<img alt="{alt}" src="{path}">'
        return f'<img alt="{alt}" src="data:image/png;base64,{b64}">'
    s = html.escape(s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl_img, s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def to_html(md_text, base):
    lines = md_text.splitlines()
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if re.match(r"^#{1,6} ", ln):
            level = len(re.match(r"^(#+) ", ln).group(1))
            out.append(f"<h{level}>{inline(ln[level + 1:], base)}</h{level}>")
            i += 1
        elif ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i]); i += 1
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in block if not re.match(r"^\|[\s:\-|]+\|$", r)]
            if not rows:
                continue
            head, body = rows[0], rows[1:]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c, base)}</th>" for c in head) + "</tr></thead><tbody>")
            for r in body:
                out.append("<tr>" + "".join(f"<td>{inline(c, base)}</td>" for c in r) + "</tr>")
            out.append("</tbody></table>")
        elif re.match(r"^\s*[-*] ", ln):
            block = []
            while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
                block.append(inline(lines[i].strip()[2:], base)); i += 1
            out.append("<ul>" + "".join(f"<li>{b}</li>" for b in block) + "</ul>")
        elif re.match(r"^\s*\d+\.\s", ln):
            block = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s", lines[i]):
                block.append(inline(re.sub(r"^\s*\d+\.\s", "", lines[i]), base)); i += 1
            out.append("<ol>" + "".join(f"<li>{b}</li>" for b in block) + "</ol>")
        elif ln.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(inline(lines[i].lstrip("> "), base)); i += 1
            out.append("<blockquote>" + "<br>".join(block) + "</blockquote>")
        elif re.match(r"^\s*---+\s*$", ln):
            out.append("<hr>"); i += 1
        else:
            out.append(f"<p>{inline(ln, base)}</p>"); i += 1
    return "\n".join(out)


def main():
    md_text = open(MD, encoding="utf-8").read()
    body = to_html(md_text, os.path.join(ROOT, "output"))
    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>创作复盘报告</title><style>{CSS}</style></head>
<body>{body}</body></html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"已生成 {OUT}（{os.path.getsize(OUT) // 1024} KB）")


if __name__ == "__main__":
    main()
