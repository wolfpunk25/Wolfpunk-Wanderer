#!/usr/bin/env bash
# Copies CIRCUITPY/ onto the mounted board.
#
# Not a plain `cp -R` or `rsync`: macOS scatters `._*` AppleDouble sidecar
# files across FAT volumes, and CircuitPython's `import` chokes trying to
# load `._code.py` etc. This copies with rsync's --exclude, then sweeps the
# destination for any that snuck in anyway (Finder can add them back just
# from the volume being open).
set -euo pipefail

DEST="${1:-/Volumes/CIRCUITPY}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../CIRCUITPY" && pwd)"

if [ ! -d "$DEST" ]; then
    echo "error: $DEST not found - is CIRCUITPY mounted? See README.md's Installing section." >&2
    exit 1
fi

echo "Copying $SRC -> $DEST"
rsync -av --delete \
    --exclude '.*' \
    --exclude '.fseventsd' \
    --exclude '.Trashes' \
    --exclude 'lib' \
    "$SRC/" "$DEST/"

echo "Sweeping AppleDouble files from $DEST"
find "$DEST" -name '._*' -delete

echo "Done. lib/ was left untouched - install/update libraries with circup separately."
