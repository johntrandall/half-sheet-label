"""Imposition geometry: fit at 100%, rotate-to-fit, scale-only-when-forced, placement."""
from __future__ import annotations

import pytest
from pypdf import PdfReader

from half_sheet_label.impose import (CELL_H, LETTER_H, LETTER_W, LabelTooBig,
                                     _transformed_bbox, impose)
from conftest import requires_gs

PT = 72.0


def _summary(blank_pdf, tmp_path, w_in, h_in, half="top", **kw):
    src = blank_pdf(f"in-{w_in}x{h_in}.pdf", w_in, h_in)
    out = tmp_path / "out.pdf"
    return impose(src, out, half, **kw), out


def test_output_is_letter(blank_pdf, tmp_path):
    _, out = _summary(blank_pdf, tmp_path, 4, 6)
    page = PdfReader(str(out)).pages[0]
    assert round(float(page.mediabox.width)) == round(LETTER_W)
    assert round(float(page.mediabox.height)) == round(LETTER_H)


def test_portrait_4x6_rotates_to_fit_at_100pct(blank_pdf, tmp_path):
    s, _ = _summary(blank_pdf, tmp_path, 4, 6)
    assert s["rotated_deg"] == 90      # 6in tall > 5.5in cell → rotate
    assert s["scale"] == 1.0
    assert s["actual_size"] is True


def test_landscape_that_fits_stays_unrotated_100pct(blank_pdf, tmp_path):
    s, _ = _summary(blank_pdf, tmp_path, 5.83, 4.13)
    assert s["rotated_deg"] == 0
    assert s["actual_size"] is True


def test_no_rotate_flag_keeps_upright(blank_pdf, tmp_path):
    # 4×6 upright is too tall for the 5.5in cell, so --no-rotate must scale it
    # (not rotate) — verifies the flag suppresses rotation.
    s, _ = _summary(blank_pdf, tmp_path, 4, 6, allow_rotate=False, allow_scale=True)
    assert s["rotated_deg"] == 0
    assert s["actual_size"] is False


def test_oversize_scales_when_allowed(blank_pdf, tmp_path):
    s, _ = _summary(blank_pdf, tmp_path, 11, 8.5, allow_scale=True)
    assert s["actual_size"] is False
    assert 0 < s["scale"] < 1
    assert s["warning"]


def test_oversize_refuses_without_scale(blank_pdf, tmp_path):
    with pytest.raises(LabelTooBig):
        _summary(blank_pdf, tmp_path, 11, 8.5, allow_scale=False)


def test_transformed_bbox_scale_only():
    assert _transformed_bbox(100, 50, 0, 2.0) == (0, 0, 200, 100)


def test_transformed_bbox_rotate_90():
    # 100×50 rotated 90° (CCW) → occupies x∈[-50,0], y∈[0,100]
    minx, miny, maxx, maxy = _transformed_bbox(100, 50, 90, 1.0)
    assert round(maxx - minx) == 50 and round(maxy - miny) == 100


@requires_gs
@pytest.mark.parametrize("half,lo,hi", [("top", CELL_H, LETTER_H), ("bottom", 0, CELL_H)])
def test_content_lands_in_correct_half(inked_pdf, tmp_path, half, lo, hi):
    import shutil
    import subprocess
    src = inked_pdf("blk.pdf", 4, 6,
                    "newpath 40 60 moveto 200 0 rlineto 0 300 rlineto -200 0 rlineto closepath fill")
    out = tmp_path / "out.pdf"
    impose(src, out, half)
    bbox = subprocess.run([shutil.which("gs"), "-q", "-dBATCH", "-dNOPAUSE",
                           "-sDEVICE=bbox", str(out)], capture_output=True, text=True).stderr
    import re
    m = re.search(r"%%HiResBoundingBox:\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", bbox)
    lly, ury = float(m.group(2)), float(m.group(4))
    assert lly >= lo - 2 and ury <= hi + 2  # ink stays within the chosen half
