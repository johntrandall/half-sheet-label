"""Smart-fit content detection — strips browser chrome, never fragments a label."""
from __future__ import annotations

from half_sheet_label.trim import content_box, smart_crop
from conftest import requires_gs

PT = 72.0

# 11×8.5 page: thin text 'header' near the top edge, thin 'footer' near the
# bottom edge, and a solid label block in the middle. Detection must strip the
# two text bands and return ~the middle block.
FULLPAGE_CHROME = """
/Helvetica findfont 8 scalefont setfont
20 588 moveto (8/13/26  Return Label  about:blank) show
20 8 moveto (about:blank                    1 of 1) show
newpath 200 150 moveto 400 0 rlineto 0 300 rlineto -400 0 rlineto closepath fill
"""

# 4×6 page whose ink fills nearly the whole page (a real label). Detection must
# return None (no benefit) — NOT trim to the densest internal strip.
FILLS_PAGE = "newpath 6 6 moveto 276 0 rlineto 0 420 rlineto -276 0 rlineto closepath fill"


@requires_gs
def test_fullpage_strips_chrome_keeps_label(inked_pdf):
    src = inked_pdf("full.pdf", 11, 8.5, FULLPAGE_CHROME)
    box = content_box(src, 11 * PT, 8.5 * PT)
    assert box is not None
    llx, lly, urx, ury = box
    # label block is x∈[200,600] (≈5.55in wide), y∈[150,450] (≈4.17in tall);
    # the chrome text bands (near y=588 and y=8) must be excluded.
    assert 350 < (urx - llx) < 460, f"width {urx-llx}"
    assert 250 < (ury - lly) < 380, f"height {ury-lly}"
    assert lly > 100 and ury < 520, "chrome bands not excluded"


@requires_gs
def test_label_filling_page_is_not_trimmed(inked_pdf):
    # Regression: a label that fills its page must return None, not a fragment.
    src = inked_pdf("fills.pdf", 4, 6, FILLS_PAGE)
    assert content_box(src, 4 * PT, 6 * PT) is None


@requires_gs
def test_dense_edge_band_is_not_cut(inked_pdf):
    # A dense (high-ink) block hugging the top edge is real label content, not
    # chrome — it must NOT be stripped even though it's near the edge.
    ps = ("newpath 40 560 moveto 500 0 rlineto 0 40 rlineto -500 0 rlineto closepath fill\n"
          "newpath 40 100 moveto 400 0 rlineto 0 300 rlineto -400 0 rlineto closepath fill")
    src = inked_pdf("dense-edge.pdf", 11, 8.5, ps)
    box = content_box(src, 11 * PT, 8.5 * PT)
    assert box is not None
    _, _, _, ury = box
    assert ury > 560, "dense top block was wrongly stripped as chrome"


@requires_gs
def test_smart_crop_returns_clipped_pdf(inked_pdf, tmp_path):
    src = inked_pdf("full2.pdf", 11, 8.5, FULLPAGE_CHROME)
    cropped, box = smart_crop(src, tmp_path)
    assert cropped is not None and cropped.is_file()
    assert box is not None


@requires_gs
def test_smart_crop_none_when_label_fills_page(inked_pdf, tmp_path):
    src = inked_pdf("fills2.pdf", 4, 6, FILLS_PAGE)
    cropped, box = smart_crop(src, tmp_path)
    assert cropped is None and box is None
