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

**Barcodes are why:** shipping/return labels carry barcodes, so nothing is ever
shrunk by default. A portrait label taller than the 5.5″ cell is *rotated* 90° to
landscape to fit — scanners tolerate rotation, but downscaling can break a
barcode. `--scale` opts into shrinking (with a warning) for the rare oversized
label. Pure Python (pypdf); no AI, no cloud round-trip required to print.

## Install

```bash
brew tap johntrandall/tap
brew install half-sheet-label
```

macOS only. Manual install for non-brew users:

```bash
git clone https://github.com/johntrandall/half-sheet-label.git
cd half-sheet-label && ./install.sh    # needs: python3, pypdf
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

# Keep a tall label upright instead of auto-rotating; or allow shrink-to-fit.
half-sheet-label label.pdf --no-rotate
half-sheet-label label.pdf --scale        # only if it won't fit even rotated (barcodes!)
```

**Reusing a half-used sheet:** always print the **top** half. To use the other
label on a partially-used sheet, **flip the sheet around** so the unused label is
in the top position, and print again. Re-feeding a sheet after the top label has
been peeled off jams the printer, so this tool never prints the bottom of an
already-used sheet.

## Where the label stock feeds from

By design, **Tray 2 holds the sticker/label stock** and Tray 1 holds regular
paper for normal printing. The CLI defaults to `label_slot = "tray-2"`.

Athena (Brother HL-L3295CDW) is currently single-tray, so until an optional
Tray 2 cassette is installed and the Brother driver exposes `tray-2`, the CLI
**automatically falls back to the hand-fed bypass slot** and prints a warning —
which is also what makes the feed-it-twice workflow work today. Once Tray 2 is
in, the default just starts working with no config change. Override per-run with
`--slot`. Normal (non-label) printing pulls from **Tray 1**, set as Athena's
CUPS default independently of this tool.

## License

MIT
