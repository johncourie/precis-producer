#!/bin/bash
# start.sh — Launch the Plant Precis Producer web interface.
# Delegates to start.py (cross-platform). Kept for backwards compatibility.

DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/start.py"
