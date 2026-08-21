# half-sheet-label

Print an already-rendered label PDF onto **Avery 8126 / 5126 half-sheet stock**
(a Letter sheet carrying two 8.5″×5.5″ peel-off shipping labels) and send it to a
laser printer. It prints the **top** half; to reuse the other label on a
partially-used sheet, flip the sheet so the free label is on top and print again.

It does **not** lay out an address for you — that's a different tool
([`mailing-label`](https://github.com/johntrandall) does 4×2 cut-and-tape). This
takes whatever label a shipping site / Preview / Click-N-Ship already produced,
places it **at 100% actual size** onto the correct half, and prints with
`print-scaling=none`.

**Barcodes are why:** shipping/return labels carry barcodes, so it avoids
shrinking. It first **smart-trims** the label out of a full page (dropping
whitespace and the browser print header/footer) so a label already ≤ the cell
stays at **100%**; a portrait label taller than the 5.5″ cell is *rotated* 90°
rather than shrunk. Only when the trimmed label still overflows does it scale
down — as little as possible — and warn you to check the barcode. `--no-scale`
refuses to shrink at all; `--no-trim` disables trimming. Trimming uses
Ghostscript; without it, oversized labels just scale more. No AI, no cloud
round-trip to print.

## Install

```bash
brew tap johntrandall/tap
brew install half-sheet-label
```

macOS only. Manual install for non-brew users:

```bash
git clone https://github.com/johntrandall/half-sheet-label.git
cd half-sheet-label && ./install.sh    # needs: python3, pypdf, ghostscript (for trimming)
```

## Usage

```bash
# Impose the label onto the top half and print it.
half-sheet-label label.pdf

# Always preview on-screen first — the imposed PDF opens in Preview, nothing prints.
half-sheet-label label.pdf --preview

# Force the bottom half (rarely needed — usually just flip the paper instead).
half-sheet-label label.pdf --half bottom

# A different printer, or more copies.
half-sheet-label label.pdf -P Apollo -c 2

# Full-page labels (e.g. a browser-printed return label) auto-trim to the label
# and scale only if needed — nothing to pass. To tune the behavior:
half-sheet-label label.pdf --no-rotate    # keep a tall label upright (don't rotate 90°)
half-sheet-label label.pdf --no-trim      # use the whole page, don't crop to the label
half-sheet-label label.pdf --no-scale     # refuse to shrink below 100% (error instead)
```

**Reusing a half-used sheet:** always print the **top** half. To use the other
label on a partially-used sheet, **flip the sheet around** so the unused label is
in the top position, and print again. Re-feeding a sheet after the top label has
been peeled off jams the printer, so this tool never prints the bottom of an
already-used sheet.

## Where the label stock feeds from — Tray 2

**Load your half-sheet label stock in Tray 2. Tray 1 stays regular paper.**

The tool sends every label to **Tray 2** by default (`label_slot = "tray-2"`,
matched case-insensitively so it works whether your driver calls the tray
`tray-2` or `Tray2`). Normal, everyday printing keeps pulling from **Tray 1**, so
you never have to swap paper. On a printer whose label tray isn't Tray 2,
override per run with `--slot "<InputSlot>"` or set `label_slot` in
`~/.config/half-sheet-label/config.toml`. If the printer has no matching tray,
the tool falls back to the hand-feed/bypass slot and warns.

At 179, Athena's Tray 2 holds the Avery 8126/5126 half-sheet labels.

## License

MIT
