"""Geometry: place a rendered label PDF onto one half of a Letter sheet.

Coordinate units are PDF points (1/72 inch). The target stock is Avery
8126/5126: a Letter (8.5x11 in) backing sheet carrying two 8.5x5.5 in peel
labels, stacked. So we print Letter media and drop content onto the top or
bottom half.

Imposition is fully deterministic — no AI. We take the source page's MediaBox
and the actual *inked* bounding box (measured by Ghostscript's `bbox` device),
fit that content into the target half (rotating 90 deg when it yields a larger
scale), and center it. The only case this can't disambiguate from geometry alone
is a source that is label+packing-slip on one page; pass --crop for that.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject

# Letter sheet and half-label footprints, in points.
LETTER_W = 612.0   # 8.5 in
LETTER_H = 792.0   # 11 in
HALF_H = 396.0     # 5.5 in

_HIRES_BBOX = re.compile(
    r"%%HiResBoundingBox:\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
)


def measure_ink(pdf_path: Path) -> tuple[float, float, float, float] | None:
    """Return the inked bounding box (llx, lly, urx, ury) of page 1, or None.

    Uses Ghostscript's bbox device. Returns None if gs is missing or fails so
    callers can fall back to the full MediaBox.
    """
    gs = shutil.which("gs")
    if not gs:
        return None
    try:
        proc = subprocess.run(
            [gs, "-q", "-dBATCH", "-dNOPAUSE", "-dFirstPage=1", "-dLastPage=1",
             "-sDEVICE=bbox", str(pdf_path)],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    # gs writes the bbox comments to stderr.
    m = None
    for line in (proc.stderr or "").splitlines():
        hit = _HIRES_BBOX.search(line)
        if hit:
            m = hit
    if not m:
        return None
    return tuple(float(m.group(i)) for i in range(1, 5))  # type: ignore[return-value]


def _target_rect(half: str, margin_pt: float) -> tuple[float, float, float, float]:
    """Usable (x, y, w, h) inside the chosen half, after margin."""
    if half not in ("top", "bottom"):
        raise ValueError(f"half must be 'top' or 'bottom', got {half!r}")
    y0 = HALF_H if half == "top" else 0.0
    return (
        margin_pt,
        y0 + margin_pt,
        LETTER_W - 2 * margin_pt,
        HALF_H - 2 * margin_pt,
    )


def _build_transform(work: tuple[float, float, float, float],
                     target: tuple[float, float, float, float],
                     allow_rotate: bool = True):
    """Map the working rect (page coords) into the target rect, rotating if it fits better."""
    wl, wb, wr, wt = work
    w, h = wr - wl, wt - wb
    tx, ty, tw, th = target
    s_norot = min(tw / w, th / h)
    s_rot = min(tw / h, th / w)
    rotate = allow_rotate and (s_rot > s_norot)
    s = s_rot if rotate else s_norot

    t = Transformation().translate(-wl, -wb)
    if rotate:
        # +90deg about origin maps [0,w]x[0,h] -> [-h,0]x[0,w]; shift back to +x.
        t = t.rotate(90).translate(h, 0)
        cw, ch = h, w
    else:
        cw, ch = w, h
    t = t.scale(s)
    off_x = tx + (tw - cw * s) / 2
    off_y = ty + (th - ch * s) / 2
    t = t.translate(off_x, off_y)
    return t, rotate, s


def impose(
    input_pdf: Path,
    output_pdf: Path,
    half: str,
    margin_in: float = 0.2,
    crop_frac: tuple[float, float, float, float] | None = None,
    allow_rotate: bool = True,
) -> dict:
    """Impose page 1 of input_pdf onto `half` of a Letter page. Returns a summary dict."""
    reader = PdfReader(str(input_pdf))
    page = reader.pages[0]
    mb = page.mediabox
    ml, mbot, mr, mtop = float(mb.left), float(mb.bottom), float(mb.right), float(mb.top)

    if crop_frac is not None:
        fl, fb, fr, ft = crop_frac
        pw, ph = mr - ml, mtop - mbot
        work = (ml + fl * pw, mbot + fb * ph, ml + fr * pw, mbot + ft * ph)
        source = "crop"
    else:
        ink = measure_ink(input_pdf)
        if ink:
            # clamp to mediabox
            work = (max(ink[0], ml), max(ink[1], mbot), min(ink[2], mr), min(ink[3], mtop))
            source = "ink-bbox"
        else:
            work = (ml, mbot, mr, mtop)
            source = "mediabox"

    margin_pt = margin_in * 72.0
    target = _target_rect(half, margin_pt)
    transform, rotated, scale = _build_transform(work, target, allow_rotate=allow_rotate)

    # Clip the source to the working rect so anything outside (e.g. a receipt)
    # is not carried along, then place it.
    page.mediabox = RectangleObject([work[0], work[1], work[2], work[3]])
    page.cropbox = RectangleObject([work[0], work[1], work[2], work[3]])

    writer = PdfWriter()
    blank = writer.add_blank_page(width=LETTER_W, height=LETTER_H)
    blank.merge_transformed_page(page, transform)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as fh:
        writer.write(fh)

    return {
        "half": half,
        "content_source": source,
        "work_pts": tuple(round(v, 1) for v in work),
        "rotated_90": rotated,
        "scale": round(scale, 3),
    }
