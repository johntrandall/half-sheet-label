# half-sheet-label

Print an already-rendered label PDF onto **Avery 8126 / 5126 half-sheet stock**
(a Letter sheet carrying two 8.5″×5.5″ peel-off shipping labels) and send it to a
laser printer's bypass tray. It remembers whether the next label goes on the
**top** or **bottom** half, so you can run one sheet through the printer twice
and use both labels.

It does **not** lay out an address for you — that's a different tool
([`mailing-label`](https://github.com/johntrandall) does 4×2 cut-and-tape). This
takes whatever label a shipping site / Preview / Click-N-Ship already produced,
scales and centers it onto the correct half, and prints. Imposition is fully
deterministic (Ghostscript measures the inked area; no AI, no cloud round-trip
required to print).

## Install

```bash
brew tap johntrandall/tap
brew install half-sheet-label
```

Requires macOS and Ghostscript (pulled in automatically by the formula).

Manual install for non-brew users:

```bash
git clone https://github.com/johntrandall/half-sheet-label.git
cd half-sheet-label && ./install.sh    # needs: python3, ghostscript, pypdf
```

## Usage

```bash
# Print onto the remembered next half (top on a fresh sheet), then flip the memory.
half-sheet-label label.pdf

# Always preview on-screen first — the imposed PDF opens in Preview, nothing prints.
half-sheet-label label.pdf --preview

# Force a specific half.
half-sheet-label label.pdf --half bottom

# See / reset which half is next for a printer.
half-sheet-label --status
half-sheet-label --reset top

# A different printer, more copies, or a busy page you need to crop to the label.
half-sheet-label label.pdf -P Apollo -c 2
half-sheet-label label.pdf --crop 0,0.5,1,1     # top-left→ isolate top half of the source
```

**Workflow for both labels on one sheet:**

1. `half-sheet-label first.pdf` → prints on the **top** half. Take the sheet out.
2. Put the *same sheet* back in the bypass tray.
3. `half-sheet-label second.pdf` → it now defaults to the **bottom** half.

The CLI always shows `▶ TOP HALF` / `▶ BOTTOM HALF` before printing so you can
confirm or override — the remembered value is a convenience, never blind.

## Which half is "next" — and sharing it across Macs

The top/bottom state is a property of the *physical printer and the half-used
sheet*, not of a person. By default it's stored per-user at
`$XDG_STATE_HOME/half-sheet-label/state.json` (i.e. `~/.local/state/…`).

Optionally, a tiny **Cloudflare Worker** (`worker/`) can hold one shared counter
for the whole household — no NAS, no mount. If the network is unreachable the
CLI **falls back to this machine's last-used value** and prints an offline
notice, so a shared counter never blocks a print. Enable it in `config.toml`:

```toml
[printer]
name = "Athena"

[state]
backend = "cloudflare"
url = "https://half-sheet-label-state.<subdomain>.workers.dev"
token = "…shared secret…"
```

See [`docs/config.example.toml`](docs/config.example.toml) and
[`worker/README.md`](worker/README.md).

## Where the label stock feeds from

Today Athena (Brother HL-L3295CDW) is a single-tray printer, so label stock
feeds one sheet at a time from the front **bypass tray** — which is what makes
the feed-it-twice workflow natural. The CLI sends `-o InputSlot=by-pass-tray` by
default; override per-run with `--slot` or permanently with `label_slot` in
config.

**Planned:** dedicate an optional lower cassette (**Tray 2**) to label stock so
you don't hand-feed. When that tray is installed and the Brother driver exposes
`tray-2`, set `label_slot = "tray-2"`. Normal (non-label) printing pulls from
**Tray 1**, set as Athena's CUPS default independently of this tool.

## License

MIT
