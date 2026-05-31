"""Chuyển một file Markdown sang DOCX và PDF (tiếng Việt).

Dùng để xuất tài liệu marketing/brochure ra file gửi cho khách hàng.

    python -m scripts.md_to_files <input.md> <output_basename>

Tạo <output_basename>.docx và <output_basename>.pdf.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Khoảng mã emoji/symbol không có trong font DejaVu — bỏ khi render file.
_EMOJI_RE = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff✨✅❌⭐✅]+",
    flags=re.UNICODE,
)


def _clean(text: str) -> str:
    """Bỏ markup inline đơn giản (**, `, |) và emoji cho bản in."""
    text = text.replace("**", "").replace("`", "")
    text = _EMOJI_RE.sub("", text)
    return text.strip()


def md_to_docx(md: str, out_path: str) -> None:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    in_table: list[list[str]] = []

    def flush_table():
        nonlocal in_table
        rows = [r for r in in_table if not all(set(c.strip()) <= {"-", ":"} for c in r)]
        if rows:
            t = doc.add_table(rows=0, cols=len(rows[0]))
            t.style = "Light Grid Accent 1"
            for r in rows:
                cells = t.add_row().cells
                for i, val in enumerate(r):
                    if i < len(cells):
                        cells[i].text = _clean(val)
        in_table = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("|") and "|" in line[1:]:
            in_table.append([c for c in line.strip().strip("|").split("|")])
            continue
        if in_table:
            flush_table()
        if not line.strip():
            continue
        if line.startswith("# "):
            doc.add_heading(_clean(line[2:]), level=0)
        elif line.startswith("## "):
            doc.add_heading(_clean(line[3:]), level=1)
        elif line.startswith("### "):
            doc.add_heading(_clean(line[4:]), level=2)
        elif line.startswith("> "):
            p = doc.add_paragraph(_clean(line[2:]))
            p.runs[0].italic = True if p.runs else False
        elif line.lstrip().startswith(("- ", "* ", "+ ")):
            doc.add_paragraph(_clean(line.lstrip()[2:]), style="List Bullet")
        elif line.startswith("---"):
            doc.add_paragraph("")
        else:
            doc.add_paragraph(_clean(line))
    if in_table:
        flush_table()
    doc.save(out_path)


_FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
]


def _font(name: str) -> str:
    for d in _FONT_DIRS:
        p = Path(d) / name
        if p.exists():
            return str(p)
    raise SystemExit("Thiếu font DejaVu (cài fonts-dejavu-core).")


def md_to_pdf(md: str, out_path: str) -> None:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", _font("DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", _font("DejaVuSans-Bold.ttf"))
    pdf.add_page()
    w = pdf.epw

    table: list[list[str]] = []

    def flush_table():
        nonlocal table
        rows = [r for r in table if not all(set(c.strip()) <= {"-", ":"} for c in r)]
        if rows:
            ncol = max(len(r) for r in rows)
            colw = w / ncol
            for ridx, r in enumerate(rows):
                pdf.set_font("DejaVu", "B" if ridx == 0 else "", 8)
                y0 = pdf.get_y()
                x0 = pdf.get_x()
                # tính chiều cao hàng theo ô cao nhất
                heights = []
                for c in r:
                    lines = pdf.multi_cell(colw, 5, _clean(c), dry_run=True, output="LINES")
                    heights.append(max(1, len(lines)) * 5)
                rowh = max(heights) if heights else 5
                if y0 + rowh > pdf.h - pdf.b_margin:
                    pdf.add_page()
                    y0 = pdf.get_y()
                for i in range(ncol):
                    txt = _clean(r[i]) if i < len(r) else ""
                    x = x0 + i * colw
                    pdf.set_xy(x, y0)
                    pdf.multi_cell(colw, 5, txt, border=1, align="L", max_line_height=5)
                pdf.set_xy(x0, y0 + rowh)
        table = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("|") and "|" in line[1:]:
            table.append([c for c in line.strip().strip("|").split("|")])
            continue
        if table:
            flush_table()
        if not line.strip() or line.startswith("---"):
            pdf.ln(2)
            continue
        if line.startswith("# "):
            pdf.set_font("DejaVu", "B", 18)
            pdf.multi_cell(w, 9, _clean(line[2:]))
        elif line.startswith("## "):
            pdf.set_font("DejaVu", "B", 14)
            pdf.multi_cell(w, 8, _clean(line[3:]))
        elif line.startswith("### "):
            pdf.set_font("DejaVu", "B", 12)
            pdf.multi_cell(w, 7, _clean(line[4:]))
        elif line.startswith("> "):
            pdf.set_font("DejaVu", "", 11)
            pdf.multi_cell(w, 6, _clean(line[2:]))
        elif line.lstrip().startswith(("- ", "* ", "+ ")):
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(w, 6, f"  •  {_clean(line.lstrip()[2:])}")
        else:
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(w, 6, _clean(line))
    if table:
        flush_table()
    pdf.output(out_path)


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Dùng: python -m scripts.md_to_files <input.md> <output_basename>")
    src = Path(sys.argv[1]).read_text(encoding="utf-8")
    base = sys.argv[2]
    md_to_docx(src, f"{base}.docx")
    md_to_pdf(src, f"{base}.pdf")
    print(f"Đã tạo: {base}.docx và {base}.pdf")


if __name__ == "__main__":
    main()
