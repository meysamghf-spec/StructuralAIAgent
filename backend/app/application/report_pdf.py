"""Calculation report as PDF: a tiny Markdown subset (headings, bullets, tables, bold/code) rendered with PyMuPDF Story.

Persian text is shaped and laid out right-to-left by MuPDF; no external fonts are needed.
"""

from __future__ import annotations

import html
import re


def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def markdown_to_html(md: str, rtl: bool = False) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i, in_list = 0, False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            close_list()
            head = [c.strip() for c in ln.strip("|").split("|")]
            out.append('<table border="1" cellpadding="3" style="border-collapse:collapse;font-size:8pt;width:100%"><tr>'
                       + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                out.append("<tr>" + "".join(f"<td>{_inline(c.strip())}</td>" for c in lines[i].strip().strip("|").split("|")) + "</tr>")
                i += 1
            out.append("</table>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        if m:
            close_list()
            n = min(len(m.group(1)) + 1, 5)
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
        elif re.match(r"^\s*[-*]\s+", ln):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(re.sub(r'^\s*[-*]\s+', '', ln))}</li>")
        elif ln.strip():
            close_list()
            out.append(f"<p>{_inline(ln)}</p>")
        else:
            close_list()
        i += 1
    close_list()
    return f'<html><body dir="{"rtl" if rtl else "ltr"}" style="font-size:9.5pt">{"".join(out)}</body></html>'


def markdown_to_pdf(md: str, *, rtl: bool = False, title: str = "SAIA report") -> bytes:
    import pymupdf

    story = pymupdf.Story(html=markdown_to_html(md, rtl))
    import io

    buf = io.BytesIO()
    w = pymupdf.DocumentWriter(buf)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (36, 40, -36, -40)
    more = 1
    while more:
        dev = w.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        w.end_page()
    w.close()
    doc = pymupdf.open("pdf", buf.getvalue())
    doc.set_metadata({"title": title, "producer": "SAIA", "creator": "SAIA"})
    return doc.tobytes(deflate=True)
