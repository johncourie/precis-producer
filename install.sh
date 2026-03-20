#!/bin/bash
# install.sh — Interactive installer for Plant Precis Producer.
#
# Power-user path: runs all install steps with confirmation prompts
# at permission-sensitive steps (poppler install, pip install).
#
# Usage: ./install.sh

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/install_steps.sh"

echo ""
echo "  Plant Precis Producer — Installer"
echo "  ─────────────────────────────────"
echo ""

# ── Step 1: Python ───────────────────────────────────────────────────────

_info "Step 1/5: Checking Python..."
step_check_python

# ── Step 2: Poppler ──────────────────────────────────────────────────────

echo ""
_info "Step 2/5: Checking poppler (pdftotext)..."
if command -v pdftotext &>/dev/null; then
    _ok "pdftotext already installed"
else
    echo "  pdftotext is required but not installed."
    read -rp "  Install poppler now? [Y/n] " yn
    case "${yn:-Y}" in
        [Yy]*|"") step_install_poppler ;;
        *) _warn "Skipped. Install poppler manually before using the tool." ;;
    esac
fi

# ── Step 3: Python deps ─────────────────────────────────────────────────

echo ""
_info "Step 3/5: Python dependencies..."
echo "  Will run: pip3 install -e ."
read -rp "  Continue? [Y/n] " yn
case "${yn:-Y}" in
    [Yy]*|"") step_install_python_deps ;;
    *) _warn "Skipped. Run 'pip3 install -e .' manually." ;;
esac

# ── Step 4: Config files ────────────────────────────────────────────────

echo ""
_info "Step 4/5: Configuration files..."
step_write_configs

# ── Step 5: Verify ──────────────────────────────────────────────────────

echo ""
_info "Step 5/5: Verifying installation..."
step_verify_install

# ── Done ─────────────────────────────────────────────────────────────────

echo ""
echo "  ─────────────────────────────────"
echo "  Installation complete."
echo ""
echo "  To start: ./start.sh"
echo "  Or:       python3 server.py"
echo ""

read -rp "  Launch now? [Y/n] " yn
case "${yn:-Y}" in
    [Yy]*|"") step_launch ;;
    *) echo "  Run ./start.sh when ready." ;;
esac
