#!/data/data/com.termux/files/usr/bin/bash

cd ~/slh_clean || exit 1

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "USAGE: ./ops/diff.sh snap1 snap2"
  exit 1
fi

DIR1="ops/snapshots/$1"
DIR2="ops/snapshots/$2"

if [ ! -d "$DIR1" ] || [ ! -d "$DIR2" ]; then
  echo "❌ Snapshot missing"
  exit 1
fi

echo "🔍 DIFF between $1 and $2"
diff -ru "$DIR1" "$DIR2" | head -200
