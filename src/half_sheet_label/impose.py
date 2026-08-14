"""Geometry: place a rendered label PDF onto one half of a Letter sheet.

The target stock is Avery 8126/5126/5526: a Letter (8.5×11 in) backing sheet
carrying two 8.5×5.5 in peel labels, stacked. So we print Letter media and drop
content onto the top or bottom half.

CORRECTNESS RULE (ported from ~/Library/Personal/half-sheet-label, 2026-06-24):
shipping/return labels carry barcodes. Everything is placed at **100% actual
size** and printed with CUPS `print-scaling=none`. A portrait label taller than
the 5.5 in cell is ROTATED 90° to landscape (which fits 8.5×5.5) rather than
shrunk — scanners tolerate rotation, but downscaling a barcode below its minimum
module width breaks scanning. Only `--scale` (allow_scale=True) shrinks, with a
warning. This is a domain invariant; do not "optimize" it into scale-to-fill.
"""

from __future__ import annotations

import math
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation

PT = 72.0
LETTER_W = 8.5 * PT   # 612
LETTER_H = 11.0 * PT  # 792
CELL_W = 8.5 * PT     # 612  full width
CELL_H = 5.5 * PT     # 396  half height


class LabelTooBig(ValueError):
    """Raised when a label won't fit the 8.5×5.5 cell even rotated, without --scale."""


def _transformed_bbox(w: float, h: float, deg: int, s: float):
    """Bounding box of a w×h box after scale s then rotation deg (degrees CCW)."""
    rad = math.radians(deg)
    cos, sin = math.cos(rad), math.sin(rad)
    xs, ys = [], []
    for x, y in ((0, 0), (w, 0), (0, h), (w, h)):
        sx, sy = x * s, y * s
        xs.append(sx * cos - sy * sin)
        ys.append(sx * sin + sy * cos)
    return min(xs), min(ys), max(xs), max(ys)


def impose(
    input_pdf: Path,
    output_pdf: Path,
    half: str,
    allow_rotate: bool = True,
    allow_scale: bool = False,
) -> dict:
    """Place page 1 of input_pdf, at 100% size, onto `half` of a blank Letter page.

    Returns a summary dict. Raises LabelTooBig if the label overflows the cell and
    allow_scale is False.
    """
    if half not in ("top", "bottom"):
        raise ValueError(f"half must be 'top' or 'bottom', got {half!r}")

    page = PdfReader(str(input_pdf)).pages[0]
    page.transfer_rotation_to_content()  # bake /Rotate; we control orientation
    vw, vh = float(page.mediabox.width), float(page.mediabox.height)

    def fits(w, h):
        return w <= CELL_W + 0.5 and h <= CELL_H + 0.5

    deg = 0
    if not fits(vw, vh) and allow_rotate and fits(vh, vw):
        deg = 90
    placed_w, placed_h = (vh, vw) if deg == 90 else (vw, vh)

    s = 1.0
    warning = None
    if not fits(placed_w, placed_h):
        s = min(CELL_W / placed_w, CELL_H / placed_h)
        if not allow_scale:
            raise LabelTooBig(
                f"'{input_pdf.name}' is {placed_w / PT:.2f}\" × {placed_h / PT:.2f}\" and "
                f"won't fit the 8.5×5.5 cell even rotated. Re-run with --scale to shrink "
                f"to {s * 100:.0f}% (may affect barcode scanning)."
            )
        warning = f"scaled to {s * 100:.0f}% to fit — verify barcodes still scan"

    cell_oy = CELL_H if half == "top" else 0.0
    minx, miny, maxx, maxy = _transformed_bbox(vw, vh, deg, s)
    tx = (CELL_W - (maxx - minx)) / 2 - minx
    ty = cell_oy + (CELL_H - (maxy - miny)) / 2 - miny

    base = PageObject.create_blank_page(width=LETTER_W, height=LETTER_H)
    base.merge_transformed_page(page, Transformation().scale(s).rotate(deg).translate(tx, ty))
    writer = PdfWriter()
    writer.add_page(base)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as fh:
        writer.write(fh)

    return {
        "half": half,
        "rotated_deg": deg,
        "scale": round(s, 3),
        "actual_size": s == 1.0,
        "source_size_in": (round(vw / PT, 2), round(vh / PT, 2)),
        "warning": warning,
    }
