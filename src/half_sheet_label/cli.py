"""half-sheet-label command line.

Ties together: config -> state backend -> imposition -> printing.

Half selection (per John, 2026-08-13):
  * default (no --half): use the REMEMBERED next half, show it, print, then flip
    the remembered value. "Last use drives the next default."
  * --half top|bottom: explicit override; after printing on half X the next
    default is still set to the other half of that sheet.
Network-unreachable behavior: the cloudflare backend falls back to this
machine's last-used value (see state.py) and the CLI prints an offline notice.
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
from .impose import impose
from .state import _other, get_backend

BYPASS_SLOT = "by-pass-tray"


def _resolve_crop(args, cfg) -> tuple[float, float, float, float] | None:
    if args.crop:
        parts = [float(x) for x in args.crop.split(",")]
        if len(parts) != 4:
            raise SystemExit("--crop expects l,b,r,t fractions, e.g. 0,0.5,1,1")
        return tuple(parts)  # type: ignore[return-value]
    if args.source:
        crop = cfg.get("sources", {}).get(args.source, {}).get("crop")
        if crop:
            return tuple(float(x) for x in crop)  # type: ignore[return-value]
    return None


def _banner(half: str, summary: dict, printer: str, offline: bool) -> None:
    arrow = "▶"
    rot = " (rotated 90°)" if summary["rotated_90"] else ""
    print(f"\n  {arrow} {half.upper()} HALF  →  {printer}{rot}")
    print(f"    content: {summary['content_source']}   scale: {summary['scale']}×")
    if offline:
        print("    ⚠ shared state offline — using THIS machine's last-used value")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="half-sheet-label",
        description="Impose a rendered label PDF onto Avery 8126/5126 half-sheet "
                    "(5.5×8.5, 2-up) stock and print to the bypass tray.",
    )
    ap.add_argument("input", nargs="?", help="label PDF to impose")
    ap.add_argument("-P", "--printer", help="CUPS printer (default: config or Athena)")
    ap.add_argument("--half", choices=["auto", "top", "bottom"], default="auto",
                    help="which half to print on (default: auto = remembered next half)")
    ap.add_argument("-p", "--preview", action="store_true",
                    help="impose and open in Preview WITHOUT printing (half not advanced)")
    ap.add_argument("--margin", type=float, help="inches inside the half-label (default 0.2)")
    ap.add_argument("--crop", help="isolate label from a busy page: l,b,r,t fractions 0–1")
    ap.add_argument("--source", help="named crop preset from config [sources.NAME]")
    ap.add_argument("--no-rotate", action="store_true",
                    help="keep the label upright even if rotating 90° would print larger")
    ap.add_argument("-c", "--copies", type=int, default=1)
    ap.add_argument("--slot", help=f"CUPS InputSlot (default: {BYPASS_SLOT})")
    ap.add_argument("--no-advance", action="store_true",
                    help="print but do NOT change the remembered half")
    ap.add_argument("--status", action="store_true", help="show the remembered next half and exit")
    ap.add_argument("--reset", choices=["top", "bottom"], help="set the remembered next half and exit")
    ap.add_argument("--dry-run", action="store_true", help="print the lp command instead of running it")
    ap.add_argument("--config", help="path to config.toml")
    ap.add_argument("-V", "--version", action="version", version=f"half-sheet-label {__version__}")
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config) if args.config else None)
    printer = (args.printer
               or cfg.get("printer", {}).get("name")
               or os.environ.get("HALF_SHEET_LABEL_PRINTER")
               or "Athena")
    backend = get_backend(cfg)

    if args.reset:
        backend.set_half(printer, args.reset)
        print(f"{printer}: next label set to {args.reset.upper()} half")
        return 0

    if args.status:
        nh = backend.next_half(printer)
        note = "  (offline — local value)" if getattr(backend, "degraded", False) else ""
        print(f"{printer}: next label → {nh.upper()} half{note}")
        return 0

    if not args.input:
        ap.error("input PDF required (or use --status / --reset)")
    input_pdf = Path(args.input).expanduser()
    if not input_pdf.is_file():
        ap.error(f"no such file: {input_pdf}")

    half = backend.next_half(printer) if args.half == "auto" else args.half
    crop = _resolve_crop(args, cfg)
    margin = args.margin if args.margin is not None else cfg.get("layout", {}).get("margin_in", 0.2)

    out = Path(tempfile.mkdtemp(prefix="half-sheet-label-")) / f"{input_pdf.stem}-{half}.pdf"
    summary = impose(input_pdf, out, half, margin_in=margin, crop_frac=crop,
                     allow_rotate=not args.no_rotate)
    offline = getattr(backend, "degraded", False)
    _banner(half, summary, printer, offline)

    if args.preview:
        subprocess.run(["open", "-a", "Preview", str(out)], check=False)
        print(f"\n  PREVIEW ONLY — not printed, half NOT advanced.\n  imposed PDF: {out}")
        return 0

    slot = args.slot or cfg.get("printer", {}).get("label_slot", BYPASS_SLOT)
    lp_cmd = ["lp", "-d", printer, "-o", f"InputSlot={slot}", "-o", "media=Letter",
              "-n", str(args.copies), str(out)]
    if args.dry_run:
        print("\n  DRY RUN:", " ".join(lp_cmd))
        return 0

    result = subprocess.run(lp_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write((result.stderr or result.stdout).strip() + "\n")
        sys.stderr.write("  PRINT FAILED — remembered half NOT advanced.\n")
        return result.returncode
    if result.stdout.strip():
        print(" ", result.stdout.strip())

    if not args.no_advance:
        new_default = _other(half)
        backend.set_half(printer, new_default)
        note = "  (offline — saved locally)" if getattr(backend, "degraded", False) else ""
        print(f"  next default for {printer}: {new_default.upper()} half{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
