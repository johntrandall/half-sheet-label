"""half-sheet-label command line.

Ties together: config -> imposition -> printing.

Always prints the TOP half by default (per John, 2026-08-14). Re-feeding a sheet
after the top label has been peeled off jams the printer, so there is no
top/bottom counter: to reuse a partially-used sheet, flip it so the free label is
on top and print again. --half bottom is a rarely-needed manual override.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__
from .config import load_config
from .impose import LabelTooBig, impose

# Label stock lives in Tray 2 (sticker paper) by design; Athena's Tray 1 holds
# regular paper for normal printing. Until an optional Tray 2 cassette is
# installed and the driver exposes "tray-2", we fall back to the hand-fed
# bypass slot (see _resolve_slot).
DEFAULT_LABEL_SLOT = "tray-2"
FALLBACK_SLOT = "by-pass-tray"


def _printer_slots(printer: str) -> list[str] | None:
    """Available InputSlot values for a printer, via lpoptions. None if unknown."""
    try:
        out = subprocess.run(["lpoptions", "-p", printer, "-l"],
                             capture_output=True, text=True, timeout=5).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    for line in out.splitlines():
        if line.startswith("InputSlot"):
            values = line.split(":", 1)[1].split()
            return [v.lstrip("*") for v in values]
    return None


def _resolve_slot(printer: str, requested: str) -> str:
    """Use the requested slot, or fall back to the bypass tray with a warning
    if the printer doesn't expose it yet (e.g. Tray 2 not installed)."""
    slots = _printer_slots(printer)
    if slots is None or requested in slots:
        return requested
    fallback = FALLBACK_SLOT if FALLBACK_SLOT in slots else (slots[0] if slots else requested)
    print(f"  ⚠ '{requested}' not available on {printer} "
          f"(slots: {', '.join(slots)}) — using '{fallback}'")
    return fallback


def _banner(half: str, summary: dict, printer: str) -> None:
    rot = " (rotated 90°)" if summary["rotated_deg"] else ""
    size = "100% actual size" if summary["actual_size"] else f"scaled {summary['scale']}×"
    w, h = summary["source_size_in"]
    print(f"\n  ▶ {half.upper()} HALF  →  {printer}{rot}")
    print(f"    label {w}×{h}in @ {size}")
    if summary.get("warning"):
        print(f"    ⚠ {summary['warning']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="half-sheet-label",
        description="Impose a rendered label PDF onto Avery 8126/5126 half-sheet "
                    "(5.5×8.5, 2-up) stock and print to the bypass tray.",
    )
    ap.add_argument("input", nargs="?", help="label PDF to impose")
    ap.add_argument("-P", "--printer", help="CUPS printer (default: config or Athena)")
    ap.add_argument("--half", choices=["top", "bottom"], default="top",
                    help="which half to print on (default: top — flip the paper to reuse "
                         "the other label; re-feeding a peeled sheet jams the printer)")
    ap.add_argument("-p", "--preview", action="store_true",
                    help="impose and open in Preview WITHOUT printing (half not advanced)")
    ap.add_argument("--no-rotate", action="store_true",
                    help="don't rotate a too-tall label to landscape to make it fit")
    ap.add_argument("--scale", action="store_true",
                    help="allow shrinking below 100%% if a label won't fit even rotated "
                         "(barcodes may stop scanning)")
    ap.add_argument("-c", "--copies", type=int, default=1)
    ap.add_argument("--slot", help=f"CUPS InputSlot (default: config label_slot or {DEFAULT_LABEL_SLOT})")
    ap.add_argument("--dry-run", action="store_true", help="print the lp command instead of running it")
    ap.add_argument("--config", help="path to config.toml")
    ap.add_argument("-V", "--version", action="version", version=f"half-sheet-label {__version__}")
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config) if args.config else None)
    printer = (args.printer
               or cfg.get("printer", {}).get("name")
               or os.environ.get("HALF_SHEET_LABEL_PRINTER")
               or "Athena")
    if not args.input:
        ap.error("input PDF required")
    input_pdf = Path(args.input).expanduser()
    if not input_pdf.is_file():
        ap.error(f"no such file: {input_pdf}")

    half = args.half

    out = Path(tempfile.mkdtemp(prefix="half-sheet-label-")) / f"{input_pdf.stem}-{half}.pdf"
    try:
        summary = impose(input_pdf, out, half,
                         allow_rotate=not args.no_rotate, allow_scale=args.scale)
    except LabelTooBig as exc:
        ap.error(str(exc))
    _banner(half, summary, printer)

    if args.preview:
        subprocess.run(["open", "-a", "Preview", str(out)], check=False)
        print(f"\n  PREVIEW ONLY — not printed.\n  imposed PDF: {out}")
        return 0

    requested_slot = args.slot or cfg.get("printer", {}).get("label_slot", DEFAULT_LABEL_SLOT)
    slot = _resolve_slot(printer, requested_slot)
    lp_cmd = ["lp", "-d", printer, "-o", f"InputSlot={slot}", "-o", "media=Letter",
              "-o", "print-scaling=none", "-n", str(args.copies), str(out)]
    if args.dry_run:
        print("\n  DRY RUN:", " ".join(lp_cmd))
        return 0

    result = subprocess.run(lp_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write((result.stderr or result.stdout).strip() + "\n")
        return result.returncode
    if result.stdout.strip():
        print(" ", result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
