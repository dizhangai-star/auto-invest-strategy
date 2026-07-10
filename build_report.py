"""
build_report — stitch the committed results/*.md + *.png into one self-contained HTML page.

Separate from backtest.py on purpose: the engine owns the numbers, this only *presents*
the markdown/PNG it already wrote. No new figures are computed here, so the report can
never drift from the reference snapshots. Output: docs/index.html (single file, PNGs
embedded as base64 — portable, opens offline, published via GitHub Pages from /docs).

Run:  python3 build_report.py    (after backtest.py has produced the results/)
Deps: none beyond the standard library.
"""
from __future__ import annotations
import base64
import html
import re
from pathlib import Path

# Ordered sections: (markdown file, optional PNG to embed after it).
SECTIONS = [
    ("results/baseline.md", "backtest_charts.png"),
    ("results/random_windows.md", "results/random_windows.png"),
    ("results/sprint2_overlays.md", "results/sprint2_overlays.png"),
    ("results/sprint3_tax_cadence.md", "results/sprint3_tax_cadence.png"),
]
OUT = "docs/index.html"          # GitHub Pages source: main branch /docs folder


# --- tiny markdown -> HTML (only the subset our results/*.md use) ---------------------
def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _render_table(rows: list[str]) -> str:
    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]
    head = "".join(f"<th>{_inline(c)}</th>" for c in cells(rows[0]))
    body = "".join(
        "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells(r)) + "</tr>"
        for r in rows[2:]
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    def flush_list():
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + "</ul>")
            items.clear()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        is_sep = bool(nxt) and set(nxt) <= set("|-: ") and "-" in nxt
        if line.startswith("|") and is_sep:                      # GFM table
            flush_para(); flush_list()
            tbl = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl.append(lines[i]); i += 1
            out.append(_render_table(tbl))
            continue
        if not line:
            flush_para(); flush_list()
        elif line.startswith("## "):
            flush_para(); flush_list(); out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            flush_para(); flush_list(); out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("- "):
            flush_para(); items.append(line[2:])
        else:
            flush_list(); para.append(line)
        i += 1
    flush_para(); flush_list()
    return "\n".join(out)


def _img(path: str) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{Path(path).name}">'


CSS = """
:root { color-scheme: light dark; --fg:#1a1a1a; --bg:#fff; --muted:#666; --line:#ddd; --accent:#0b5; }
@media (prefers-color-scheme: dark) {
  :root { --fg:#e6e6e6; --bg:#161616; --muted:#9a9a9a; --line:#333; --accent:#3d9; }
}
* { box-sizing: border-box; }
body { font: 16px/1.6 -apple-system, system-ui, sans-serif; color: var(--fg); background: var(--bg);
       max-width: 860px; margin: 0 auto; padding: 2rem 1.25rem 5rem; }
h1 { font-size: 1.7rem; margin: 2.5rem 0 .5rem; }
h2 { font-size: 1.2rem; margin: 1.8rem 0 .4rem; border-bottom: 1px solid var(--line); padding-bottom: .2rem; }
section { border-top: 3px solid var(--line); margin-top: 3rem; }
section:first-of-type { border-top: none; margin-top: 0; }
p, li { color: var(--fg); }
code { background: color-mix(in srgb, var(--fg) 10%, transparent); padding: .1em .35em; border-radius: 4px;
       font-size: .88em; }
a { color: var(--accent); }
.tablewrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: .8rem 0; font-size: .92rem; }
th, td { border: 1px solid var(--line); padding: .4rem .6rem; text-align: left; white-space: nowrap; }
th { background: color-mix(in srgb, var(--fg) 6%, transparent); }
img { max-width: 100%; height: auto; margin: 1rem 0; border: 1px solid var(--line); border-radius: 6px; }
.foot { color: var(--muted); font-size: .85rem; margin-top: 4rem; border-top: 1px solid var(--line); padding-top: 1rem; }
"""


def build() -> str:
    body = []
    for md_path, png_path in SECTIONS:
        if not Path(md_path).exists():
            continue
        section = md_to_html(Path(md_path).read_text())
        section = section.replace("<table>", '<div class="tablewrap"><table>').replace(
            "</table>", "</table></div>")
        if png_path and Path(png_path).exists():
            section += _img(png_path)
        body.append(f"<section>{section}</section>")

    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>ETF Backtest &amp; DCA Analysis</title>"
        f"<style>{CSS}</style></head><body>"
        + "\n".join(body)
        + "<p class='foot'>Generated by build_report.py from the committed results/*.md and *.png. "
          "Total-return, USD, pre-tax. Regenerate: <code>python backtest.py &amp;&amp; python build_report.py</code>.</p>"
        "</body></html>"
    )
    Path(OUT).write_text(page)
    return OUT


if __name__ == "__main__":
    out = build()
    print(f"[report] wrote {out} ({len(SECTIONS)} sections stitched)")
