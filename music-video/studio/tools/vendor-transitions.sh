#!/usr/bin/env bash
# Vendor remotion-transitions (MIT) at a pinned commit into studio/transitions/.
# Never edit the vendored files; re-run this script to update them.
set -euo pipefail
SHA="${1:-58df89999661dacef23bc23d05b9d2cd978bda45}"
STUDIO="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --quiet https://github.com/GTKottman/remotion-transitions.git "$TMP/rt"
git -C "$TMP/rt" checkout --quiet "$SHA"
DEST="$STUDIO/transitions"
rm -rf "$DEST"
mkdir -p "$DEST/src"
cp -R "$TMP/rt/src/core" "$DEST/src/core"
cp "$TMP/rt/src/registry.ts" "$DEST/src/registry.ts"
rsync -a --exclude '*.png' --exclude '*.webp' --exclude '*.mp4' --exclude '*.gif' \
  "$TMP/rt/transitions/" "$DEST/transitions/"
cp "$TMP/rt/LICENSE" "$TMP/rt/TAXONOMY.md" "$TMP/rt/catalog.json" "$DEST/"
cat > "$DEST/VENDORED.md" <<EOT
# remotion-transitions (vendored)

Source: https://github.com/GTKottman/remotion-transitions at \`$SHA\`, copied $(date +%Y-%m-%d)
by \`tools/vendor-transitions.sh\`. Licence: MIT (see LICENSE). Do not edit these files.
EOT
echo "vendored remotion-transitions $SHA into $DEST"
