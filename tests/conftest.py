"""Shared test fixtures.

Blank PDFs (via pypdf) exercise the imposition math, which only reads page
geometry. Inked PDFs (via Ghostscript) are needed for trim tests, which render
the page — those are skipped when gs is absent.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest
from pypdf import PdfWriter

GS = shutil.which("gs")
requires_gs = pytest.mark.skipif(not GS, reason="ghostscript not installed")

PT = 72.0


@pytest.fixture
def blank_pdf(tmp_path):
    """Make a blank PDF of a given size in inches → path."""
    def _make(name, w_in, h_in):
        path = tmp_path / name
        wr = PdfWriter()
        wr.add_blank_page(width=w_in * PT, height=h_in * PT)
        with open(path, "wb") as fh:
            wr.write(fh)
        return path
    return _make


@pytest.fixture
def inked_pdf(tmp_path):
    """Make a PDF of size w_in×h_in with the given PostScript body (page coords in points)."""
    def _make(name, w_in, h_in, ps_body):
        if not GS:
            pytest.skip("ghostscript not installed")
        path = tmp_path / name
        ps = path.with_suffix(".ps")
        ps.write_text(f"<< /PageSize [{w_in * PT} {h_in * PT}] >> setpagedevice\n{ps_body}\nshowpage\n")
        subprocess.run([GS, "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
                        "-o", str(path), str(ps)], check=True, capture_output=True)
        return path
    return _make
