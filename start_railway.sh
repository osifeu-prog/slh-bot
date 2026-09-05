#!/bin/bash
set -e

# Canonical Railway entrypoint: bot_gateway owns both API and Telegram polling.
# Keep a single production process to avoid duplicate Telegram getUpdates polling.
echo "Starting SLH Railway gateway"
exec python3 -u -B bot_gateway.py
