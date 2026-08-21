# half-sheet-label

Print a shipping or return label PDF onto a **half-sheet peel-and-stick sticker**
— no more printing on paper, cutting the label out, and taping it to the box.

You hand it whatever label a shipping site, Amazon return, USPS Click-N-Ship, or
a browser "Save as PDF" produced; it finds the label on the page, keeps it at
**full size** so the barcode still scans, drops it onto one half of an Avery
8126/5126 half-sheet label, and prints. Two labels fit per sheet.

- **Two ways to use it:** from any app's **Print dialog** (⌘P → PDF ▾ → Half-Sheet
  Label), or from the **command line** (`half-sheet-label label.pdf`).
- **Barcode-safe:** never silently shrinks a label — see [How it works](#how-it-works).
- **macOS only.** Pure Python + Ghostscript under the hood; no cloud, no account.

---

## Install

```bash
brew tap johntrandall/tap
brew install half-sheet-label
```

That gives you the `half-sheet-label` command. To also add the **Print-dialog
entry** (so you can print labels straight from ⌘P in any app), run it once:

```bash
half-sheet-label --install-pdf-service
```

*(No Homebrew yet? Install it from https://brew.sh, then run the two lines above.)*

---

## Two ways to use it

### 1. From the Print dialog (easiest)

After `--install-pdf-service`, in **any** app showing a label:

1. **⌘P** (Print)
2. Click the **PDF ▾** menu, bottom-left of the print dialog
3. Choose **Half-Sheet Label**

It imposes the label and prints it — a notification confirms. Nothing else to do.

### 2. From the command line

```bash
half-sheet-label ~/Downloads/your-label.pdf
```

Same result. Handy in scripts, or when you already have the PDF on disk.

**Preview before printing** (opens the imposed page in Preview, prints nothing):

```bash
half-sheet-label label.pdf --preview
```

### Reusing a half-used sheet

It always prints the **top** half. To use the second label on a partly-used
sheet, **flip the sheet over** so the free label is on top, and run it again.
(Re-feeding a sheet after peeling the top label off jams the printer, so it never
prints onto the bottom of an already-used sheet.)

---

## Loading labels — Tray 2

**Load your half-sheet label stock in Tray 2. Tray 1 stays regular paper.**

The tool sends every label to **Tray 2** by default (matched case-insensitively,
so it works whether the driver names the tray `tray-2` or `Tray2`). Everyday
printing keeps pulling from Tray 1, so you never swap paper.

- **At home:** Athena is set up as a label printer — its Tray 2 is already loaded
  with the half-sheet labels.
- **Other printers:** if the label tray isn't Tray 2, override per run with
  `--slot "<InputSlot>"`, or set `label_slot` in your config (below). If the
  printer has no matching tray, it falls back to the hand-feed/bypass slot and
  warns.

Label stock: **Avery 8126 / 5126 / 5526** — two 5½″ × 8½″ labels per US-Letter
sheet.

---

## How it works

Shipping labels carry barcodes, and **shrinking a barcode can stop it from
scanning** — so this tool goes out of its way to avoid scaling:

1. **Smart-trim.** Many labels arrive as a full 8.5×11 page (a browser print,
   with the label in the middle plus a date/URL header and footer). Ghostscript
   renders the page and the tool crops to the actual label — dropping the
   surrounding whitespace *and* the browser header/footer — without cutting into
   the label itself.
2. **100% when it fits.** If the trimmed label fits the 8.5×5.5 cell, it prints
   at exactly actual size. A portrait label taller than 5.5″ is **rotated** 90°
   to fit rather than shrunk.
3. **Scale only as a last resort.** If the label still overflows, it scales down
   *as little as possible* and **warns you to check the barcode**. `--no-scale`
   refuses to scale at all (errors instead), for when you'd rather not risk it.
4. **`print-scaling=none`.** The print job tells CUPS not to re-scale, so what you
   measured is what prints.

No AI, no network round-trip — just deterministic geometry.

---

## Options

```
half-sheet-label [PDF] [options]

  --preview              impose and open in Preview; don't print
  --half {top,bottom}    which half to print on (default: top)
  --no-rotate            keep a tall label upright instead of rotating 90°
  --no-trim              use the whole page; don't crop to the label
  --no-scale             never shrink below 100% (error instead of scaling)
  -P, --printer NAME     printer to use (default: config, or Athena)
  --slot INPUTSLOT       paper source (default: config label_slot, else Tray 2)
  -c, --copies N         number of copies
  --dry-run              print the `lp` command instead of running it
  --config PATH          path to a config.toml
  --install-pdf-service      add the ⌘P Print-dialog entry, then exit
  --uninstall-pdf-service    remove the Print-dialog entry, then exit
  -V, --version
```

---

## Configuration (optional)

`~/.config/half-sheet-label/config.toml`:

```toml
[printer]
name = "Athena"          # default printer
label_slot = "tray-2"    # tray holding the label stock (case-insensitive)
```

Everything has sensible defaults; the file is optional.

---

## Troubleshooting

- **"Half-Sheet Label" isn't in the PDF menu.** Run `half-sheet-label
  --install-pdf-service`. If it still doesn't show, log out and back in
  (LaunchServices caches the menu).
- **The Print-dialog entry fails silently.** It logs to
  `~/Library/Logs/half-sheet-label-pdfservice.log`, and pops an alert on error.
- **"printer not found" / prints from the wrong tray.** Add your printer in
  System Settings first; make sure the label stock is in the tray the tool
  targets (Tray 2 by default) — use `--slot` or `label_slot` to change it.
- **Barcode won't scan.** If the tool warned it scaled below 100%, print that
  label with `--no-scale` and get the source as a clean label (not a full page
  with browser header/footer), or from the carrier's "download 4×6 label" option.
- **Nothing came out.** Check the printer isn't in an error/paused state
  (`lpstat -p <printer>`).

---

## Uninstall

```bash
half-sheet-label --uninstall-pdf-service   # remove the Print-dialog entry
brew uninstall half-sheet-label            # remove the command
brew untap johntrandall/tap                # optional
```

---

## Development

```bash
git clone https://github.com/johntrandall/half-sheet-label.git
cd half-sheet-label
uv run --with pytest --with pypdf pytest      # run the test suite
```

Layout: `impose.py` (imposition geometry), `trim.py` (label-content detection),
`pdf_service.py` (the ⌘P entry), `config.py`, `cli.py`.

## License

MIT
