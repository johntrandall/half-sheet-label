#!/usr/bin/env bash
# Reverse install.sh. Leaves config ($XDG_CONFIG_HOME/half-sheet-label) and
# state ($XDG_STATE_HOME/half-sheet-label) in place; remove those by hand if wanted.
set -euo pipefail

prefix="${XDG_DATA_HOME:-$HOME/.local/share}/half-sheet-label"
bindir="$HOME/.local/bin"

[ -L "$bindir/half-sheet-label" ] && rm -f "$bindir/half-sheet-label" && echo "removed $bindir/half-sheet-label"
[ -d "$prefix" ] && rm -rf "$prefix" && echo "removed $prefix"
echo "done. (config/state left intact — remove ~/.config/half-sheet-label and ~/.local/state/half-sheet-label if you want them gone.)"
