#!/usr/bin/env bash
# Manual install for non-Homebrew users. Idempotent.
# Creates an isolated venv and symlinks the CLI into ~/.local/bin.
# Homebrew users should instead: brew tap johntrandall/tap && brew install half-sheet-label
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prefix="${XDG_DATA_HOME:-$HOME/.local/share}/half-sheet-label"
bindir="$HOME/.local/bin"

command -v python3 >/dev/null || { echo "error: python3 not found"; exit 1; }

echo "==> creating venv at $prefix/venv"
python3 -m venv "$prefix/venv"
"$prefix/venv/bin/pip" install --quiet --upgrade pip
echo "==> installing half-sheet-label + deps"
"$prefix/venv/bin/pip" install --quiet "$here"

mkdir -p "$bindir"
ln -sf "$prefix/venv/bin/half-sheet-label" "$bindir/half-sheet-label"
echo "==> linked $bindir/half-sheet-label"

case ":$PATH:" in
  *":$bindir:"*) : ;;
  *) echo "note: $bindir is not on your PATH — add it to use 'half-sheet-label' directly." ;;
esac
echo "done. Try: half-sheet-label --status"
