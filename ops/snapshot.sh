#!/data/data/com.termux/files/usr/bin/bash

cd ~/slh_clean || exit 1

TS=$(date +%Y%m%d_%H%M%S)
SNAP_DIR="ops/snapshots/snap_$TS"

mkdir -p "$SNAP_DIR"

echo "📦 Creating snapshot: $TS"

cp -r bot_stable.py "$SNAP_DIR/" 2>/dev/null
cp -r state "$SNAP_DIR/" 2>/dev/null
cp -r *.py "$SNAP_DIR/" 2>/dev/null

echo "$TS" > ops/last_snapshot.txt

echo "✅ Snapshot saved at $SNAP_DIR"
