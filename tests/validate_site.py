from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []
        self.assets: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("target") == "_blank":
            rel = set((values.get("rel") or "").split())
            if not {"noopener", "noreferrer"}.issubset(rel):
                self.errors.append("external link lacks noopener noreferrer")
        if any(name.lower().startswith("on") for name in values):
            self.errors.append(f"inline event handler on <{tag}>")
        if tag == "img":
            source = values.get("src", "")
            if source.startswith("assets/"):
                self.assets.add(source)
            if not values.get("alt"):
                self.errors.append("image lacks alt text")
            if not values.get("width") or not values.get("height"):
                self.errors.append("image lacks intrinsic dimensions")


def main() -> int:
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(text)
    for asset in parser.assets:
        if not (ROOT / asset).is_file():
            parser.errors.append(f"missing local asset: {asset}")
    if "assets/profile.jpg" not in parser.assets:
        parser.errors.append("personal profile photograph is missing")
    if '<meta name="description"' not in text or 'application/ld+json' not in text:
        parser.errors.append("SEO metadata is incomplete")
    if parser.errors:
        raise SystemExit("\n".join(parser.errors))
    print(f"site valid; {len(parser.assets)} local assets checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
