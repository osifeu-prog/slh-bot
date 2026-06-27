#!/data/data/com.termux/files/usr/bin/bash

echo "🔍 SWARM SYSTEM SEARCH START"

BASE=~/slh_clean

echo ""
echo "📌 1. Searching environment variables..."
env | grep -i telegram || echo "NO TELEGRAM ENV VAR FOUND"

echo ""
echo "📌 2. Searching bash/profile configs..."
grep -R "TELEGRAM" ~/.bashrc ~/.profile ~/.zshrc 2>/dev/null || echo "NO SHELL CONFIG FOUND"

echo ""
echo "📌 3. Searching project files..."
grep -R "TELEGRAM" $BASE 2>/dev/null | head -50 || echo "NO PROJECT TOKENS FOUND"

echo ""
echo "📌 4. Searching for token-like strings..."
grep -R "[0-9]\{8,10\}:" $BASE 2>/dev/null | head -20 || echo "NO TOKEN PATTERNS FOUND"

echo ""
echo "📌 5. Checking running processes..."
ps -A | grep -i python || echo "NO PYTHON PROCESSES"

echo ""
echo "📌 DONE"
