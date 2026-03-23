#!/usr/bin/env bash
set -euo pipefail

VOCAB_DIR="$(cd "$(dirname "$0")/.." && pwd)/models/orbslam3"
VOCAB_FILE="$VOCAB_DIR/ORBvoc.txt"
VOCAB_URL="https://github.com/UZ-SLAMLab/ORB_SLAM3/raw/master/Vocabulary/ORBvoc.txt.tar.gz"
EXPECTED_SIZE_MB=40

mkdir -p "$VOCAB_DIR"

if [ -f "$VOCAB_FILE" ]; then
    echo "[OK] ORBvoc.txt already exists at $VOCAB_FILE"
    exit 0
fi

echo "Downloading ORB-SLAM3 vocabulary (~${EXPECTED_SIZE_MB}MB compressed)..."
TMPFILE=$(mktemp)
curl -fSL "$VOCAB_URL" -o "$TMPFILE"

echo "Extracting..."
tar -xzf "$TMPFILE" -C "$VOCAB_DIR"
rm -f "$TMPFILE"

if [ -f "$VOCAB_FILE" ]; then
    SIZE=$(du -m "$VOCAB_FILE" | cut -f1)
    echo "[OK] ORBvoc.txt downloaded (${SIZE}MB) to $VOCAB_FILE"
else
    echo "[ERROR] Extraction failed — ORBvoc.txt not found after extracting"
    exit 1
fi
