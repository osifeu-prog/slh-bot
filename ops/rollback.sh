#!/data/data/com.termux/files/usr/bin/bash

cd ~/slh_clean || exit 1

if [ -z "$1" ]; then
  echo "USAGE: ./ops/rollback.sh snap_YYYYMMDD_HHMMSS"
  exit 1
fi

TARGET="ops/snapshots/$1"

if [ ! -d "$TARGET" ]; then
  echo "❌ Snapshot not found"
  exit 1
fi

echo "♻️ Rolling back to $1"

cp -r "$TARGET"/* . 2>/dev/null

echo "✅ Rollback complete"
