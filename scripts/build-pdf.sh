#!/usr/bin/env bash
# Print the built article to src/docs/alt-xmp-favicons.pdf with headless Chrome.
#
#   npm run pdf                  # or: scripts/build-pdf.sh
#   CHROME=/path/to/chrome npm run pdf
#
# Builds the site into a temp dir under the /game11ty/ prefix (as GitHub Pages
# serves it), prints /article/, then writes the size into the article's
# `pdfSize` front matter. The size label is printed inside the PDF too, so if
# it changed, the page is rebuilt and printed once more.
set -euo pipefail

cd "$(dirname "$0")/.."

ARTICLE=src/pages/article.md
OUT=src/docs/alt-xmp-favicons.pdf
TITLE="ALT, XMP and Favicons: Image Metadata for Rights and Media Management"

if [[ -z "${CHROME:-}" ]]; then
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then CHROME=$c; break; fi
  done
fi
[[ -n "${CHROME:-}" ]] || { echo "Chrome not found; set CHROME=/path/to/chrome" >&2; exit 1; }

TMP=$(mktemp -d)
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("",0)); print(s.getsockname()[1])')
python3 -m http.server "$PORT" --directory "$TMP" >/dev/null 2>&1 &
SERVER=$!
disown "$SERVER"
trap 'kill $SERVER 2>/dev/null; rm -rf "$TMP"' EXIT

print_pdf() {
  PATH_PREFIX=/game11ty/ npx @11ty/eleventy --quiet --output="$TMP/game11ty" >/dev/null
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
    --virtual-time-budget=15000 --print-to-pdf="$OUT" \
    "http://localhost:$PORT/game11ty/article/" 2>/dev/null
  [[ -s "$OUT" ]] || { echo "Chrome produced no PDF" >&2; exit 1; }
}

size_label() {
  python3 -c "import os; print(f'{os.path.getsize(\"$OUT\")/1e6:.1f} MB')"
}

print_pdf
label=$(size_label)
if ! grep -q "^pdfSize: \"$label\"$" "$ARTICLE"; then
  sed -i.bak "s/^pdfSize: \".*\"$/pdfSize: \"$label\"/" "$ARTICLE" && rm -f "$ARTICLE.bak"
  print_pdf
  label=$(size_label)
fi

if command -v exiftool >/dev/null 2>&1; then
  exiftool -q -overwrite_original -Title="$TITLE" -Author="persephonepunch" "$OUT"
fi

pages=$(python3 - "$OUT" <<'EOF'
import re, sys
print(len(re.findall(rb"/Type\s*/Page[^s]", open(sys.argv[1], "rb").read())))
EOF
)
echo "Wrote $OUT ($pages pages, $label)"
