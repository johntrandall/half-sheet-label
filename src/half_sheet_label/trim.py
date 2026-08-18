"""Smart content detection: crop a label PDF to its real content.

Full-page labels (e.g. a return label printed from a browser) arrive as an
8.5×11 page with the label surrounded by whitespace and a thin browser
header/footer band. We render the page, find the dominant content band (dropping
those thin marginal bands), and clip the PDF to it with Ghostscript — so the
downstream imposer sees just the label and can keep it at (or near) 100%.

Pure-Python analysis (stdlib only) over a low-res grayscale render; Ghostscript
does the render and the clip. If gs is missing or detection isn't beneficial,
callers fall back to the original PDF.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_DARK = 140          # 0..255; pixels below this count as ink
_RENDER_DPI = 72


def _gs():
    return shutil.which("gs")


def _render_pgm(pdf_path: Path, dpi: int = _RENDER_DPI):
    """Render page 1 to a grayscale PGM (P5) and return (w, h, pixels) or None."""
    gs = _gs()
    if not gs:
        return None
    try:
        proc = subprocess.run(
            [gs, "-q", "-dBATCH", "-dNOPAUSE", "-dFirstPage=1", "-dLastPage=1",
             f"-r{dpi}", "-sDEVICE=pgmraw", "-sOutputFile=-", str(pdf_path)],
            capture_output=True, timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    return _parse_pgm(proc.stdout)


def _parse_pgm(data: bytes):
    if data[:2] != b"P5":
        return None
    idx, tokens = 2, []
    while len(tokens) < 3:
        while idx < len(data) and data[idx:idx + 1].isspace():
            idx += 1
        if idx < len(data) and data[idx:idx + 1] == b"#":
            while idx < len(data) and data[idx:idx + 1] != b"\n":
                idx += 1
            continue
        start = idx
        while idx < len(data) and not data[idx:idx + 1].isspace():
            idx += 1
        tokens.append(data[start:idx])
    w, h, _maxval = int(tokens[0]), int(tokens[1]), int(tokens[2])
    idx += 1  # one whitespace byte after maxval
    pix = data[idx:idx + w * h]
    if len(pix) < w * h:
        return None
    return w, h, pix


def _bands(inked: list[bool], gap: int):
    """Contiguous runs of True, merging runs separated by <= gap False rows."""
    bands, start, last, gapc = [], None, None, 0
    for i, v in enumerate(inked):
        if v:
            if start is None:
                start = i
            last, gapc = i, 0
        elif start is not None:
            gapc += 1
            if gapc > gap:
                bands.append((start, last))
                start, gapc = None, 0
    if start is not None:
        bands.append((start, last))
    return bands


def content_box(pdf_path: Path, page_w_pt: float, page_h_pt: float):
    """Return (llx, lly, urx, ury) in PDF points of the dominant content, or None.

    Drops thin marginal bands (browser header/footer) and surrounding whitespace.
    Returns None if gs is unavailable, detection fails, or the box is ~the whole
    page (no benefit).
    """
    r = _render_pgm(pdf_path)
    if not r:
        return None
    w, h, pix = r
    tbl = bytes(1 if i < _DARK else 0 for i in range(256))
    bits = pix.translate(tbl)

    row_ink = [bits[y * w:(y + 1) * w].count(1) for y in range(h)]
    total_ink = sum(row_ink)
    if total_ink == 0:
        return None
    row_thr = max(3, int(w * 0.004))
    inked = [ri > row_thr for ri in row_ink]
    bands = _bands(inked, gap=max(3, int(h * 0.012)))
    if not bands:
        return None

    # Strip ONLY browser print header/footer: a band that hugs the top/bottom
    # edge AND is thin AND carries little ink. Keep everything else (the whole
    # label, including its internal whitespace) — never fragment on the densest
    # strip. A dense barcode band is never cut (fails the low-ink test).
    edge = 0.12 * h
    thin_px = max(int(0.4 * h / (page_h_pt / 72.0)), int(0.05 * h))

    def _is_chrome(b):
        top, bot = b
        center, height = (top + bot) / 2, bot - top + 1
        near_edge = center < edge or center > (h - edge)
        band_ink = sum(row_ink[top:bot + 1])
        return near_edge and height <= thin_px and band_ink < 0.06 * total_ink

    content = [b for b in bands if not _is_chrome(b)]
    if not content:
        return None
    y0, y1 = min(b[0] for b in content), max(b[1] for b in content)

    # horizontal extent within the kept vertical span
    col = [0] * w
    for y in range(y0, y1 + 1):
        rb = bits[y * w:(y + 1) * w]
        for x in range(w):
            if rb[x]:
                col[x] += 1
    col_thr = max(2, int((y1 - y0 + 1) * 0.01))
    xs = [x for x in range(w) if col[x] > col_thr]
    if not xs:
        return None
    x0, x1 = min(xs), max(xs)

    # small padding
    px, py = int(w * 0.006), int(h * 0.006)
    x0, x1 = max(0, x0 - px), min(w - 1, x1 + px)
    y0, y1 = max(0, y0 - py), min(h - 1, y1 + py)

    sx, sy = page_w_pt / w, page_h_pt / h
    llx, urx = x0 * sx, (x1 + 1) * sx
    lly, ury = page_h_pt - (y1 + 1) * sy, page_h_pt - y0 * sy  # PGM top-left → PDF bottom-left

    if (urx - llx) > 0.92 * page_w_pt and (ury - lly) > 0.92 * page_h_pt:
        return None  # no meaningful trim (label already fills the page)
    return (llx, lly, urx, ury)


def crop_pdf(pdf_path: Path, box, out_path: Path) -> Path | None:
    """Clip pdf_path to `box` (llx,lly,urx,ury pts) via gs; return out_path or None."""
    gs = _gs()
    if not gs:
        return None
    llx, lly, urx, ury = box
    wbox, hbox = urx - llx, ury - lly
    try:
        proc = subprocess.run(
            [gs, "-q", "-o", str(out_path), "-sDEVICE=pdfwrite",
             "-dFirstPage=1", "-dLastPage=1",
             f"-dDEVICEWIDTHPOINTS={wbox:.2f}", f"-dDEVICEHEIGHTPOINTS={hbox:.2f}",
             "-dFIXEDMEDIA",
             "-c", f"<</PageOffset [ {-llx:.2f} {-lly:.2f} ]>> setpagedevice",
             "-f", str(pdf_path)],
            capture_output=True, timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0 or not out_path.is_file():
        return None
    return out_path


def smart_crop(pdf_path: Path, workdir: Path):
    """Detect the label content and clip the PDF to it.

    Returns (cropped_path, box) on success, or (None, None) if Ghostscript is
    unavailable, detection fails, or there's no meaningful margin to trim — in
    which case the caller just uses the original PDF.
    """
    from pypdf import PdfReader
    try:
        mb = PdfReader(str(pdf_path)).pages[0].mediabox
        page_w_pt, page_h_pt = float(mb.width), float(mb.height)
    except Exception:
        return None, None
    box = content_box(pdf_path, page_w_pt, page_h_pt)
    if not box:
        return None, None
    out = crop_pdf(pdf_path, box, workdir / "trimmed.pdf")
    if not out:
        return None, None
    return out, box
