#!/bin/bash
# install_steps.sh — Idempotent install functions for Plant Precis Producer.
#
# Source this file; call individual functions. Each function is safe to
# re-run — it checks current state before acting.
#
# Usage:
#   source install_steps.sh
#   step_install_poppler
#   step_install_python_deps
#   ...

set -euo pipefail

# ── Resolve project directory ────────────────────────────────────────────

PPP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PPP_PORT=7734

# ── Helpers ──────────────────────────────────────────────────────────────

_info()  { printf "\033[0;36m%s\033[0m\n" "$*"; }
_ok()    { printf "\033[0;32m✓ %s\033[0m\n" "$*"; }
_warn()  { printf "\033[0;33m⚠ %s\033[0m\n" "$*"; }
_err()   { printf "\033[0;31m✗ %s\033[0m\n" "$*"; }

_is_macos() { [[ "$(uname)" == "Darwin" ]]; }
_is_linux() { [[ "$(uname)" == "Linux" ]]; }

# ── Step functions ───────────────────────────────────────────────────────

step_check_python() {
    # Verify Python 3.9+ is available.
    if ! command -v python3 &>/dev/null; then
        _err "python3 not found."
        echo "  Install Python 3.9+ from https://python.org"
        return 1
    fi

    local ver
    ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)

    if (( major < 3 || (major == 3 && minor < 9) )); then
        _err "Python $ver found, but 3.9+ is required."
        return 1
    fi

    _ok "Python $ver"
}

step_install_poppler() {
    # Install poppler (provides pdftotext) if not present.
    if command -v pdftotext &>/dev/null; then
        _ok "pdftotext already installed"
        return 0
    fi

    _info "Installing poppler (provides pdftotext)..."

    if _is_macos; then
        if command -v brew &>/dev/null; then
            brew install poppler
        else
            _err "Homebrew not found. Install poppler manually:"
            echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            echo "  brew install poppler"
            return 1
        fi
    elif _is_linux; then
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y -qq poppler-utils
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y poppler-utils
        else
            _err "Could not detect package manager. Install poppler-utils manually."
            return 1
        fi
    else
        _err "Unsupported OS. Install pdftotext manually."
        return 1
    fi

    if command -v pdftotext &>/dev/null; then
        _ok "pdftotext installed"
    else
        _err "pdftotext installation failed"
        return 1
    fi
}

step_install_python_deps() {
    # Install Python dependencies via pip.
    _info "Installing Python dependencies..."

    cd "$PPP_DIR"
    pip3 install -e . --quiet 2>&1 | tail -1 || pip3 install -e .

    # Verify core imports
    if python3 -c "import pypdf, reportlab, fastapi, uvicorn" 2>/dev/null; then
        _ok "Python dependencies installed"
    else
        _err "Some Python packages failed to install"
        return 1
    fi
}

step_write_configs() {
    # Create books.json and config.json from examples if they don't exist.
    cd "$PPP_DIR"

    if [[ -f books.json ]]; then
        _ok "books.json exists"
    else
        cp books.example.json books.json
        _ok "books.json created from template"
    fi

    if [[ -f config.json ]]; then
        _ok "config.json exists"
    else
        # Detect Zotero and enable automatically if found
        local zotero_db="$HOME/Zotero/zotero.sqlite"
        if [[ -f "$zotero_db" ]]; then
            python3 -c "
import json
c = json.load(open('config.example.json'))
c['zotero']['enabled'] = True
json.dump(c, open('config.json','w'), indent=2)
"
            _ok "config.json created (Zotero detected and enabled)"
        else
            cp config.example.json config.json
            _ok "config.json created from template (Zotero not found)"
        fi
    fi
}

step_verify_install() {
    # Run a minimal end-to-end check.
    cd "$PPP_DIR"

    local failed=0

    # Check all required commands
    for cmd in python3 pdftotext; do
        if ! command -v "$cmd" &>/dev/null; then
            _err "Missing: $cmd"
            failed=1
        fi
    done

    # Check Python imports
    if ! python3 -c "import pypdf, reportlab, fastapi, uvicorn" 2>/dev/null; then
        _err "Python imports failed"
        failed=1
    fi

    # Check config files
    for f in books.json config.json; do
        if [[ ! -f "$f" ]]; then
            _err "Missing: $f"
            failed=1
        fi
    done

    # Check at least one index exists
    if ls _indexes/*.txt &>/dev/null; then
        local count
        count=$(ls _indexes/*.txt 2>/dev/null | wc -l | tr -d ' ')
        _ok "$count index files found"
    else
        _warn "No index files found in _indexes/"
    fi

    # Check server can start
    if python3 -c "from server import app, state; state.load()" 2>/dev/null; then
        _ok "Server loads successfully"
    else
        _err "Server failed to load"
        failed=1
    fi

    if (( failed )); then
        _err "Verification failed"
        return 1
    fi

    _ok "All checks passed"
}

step_launch() {
    # Start the web server and open the browser.
    cd "$PPP_DIR"

    local url="http://localhost:$PPP_PORT"

    _info "Starting Plant Precis Producer at $url"

    # Open browser after a short delay
    (sleep 1.5 && {
        if _is_macos; then
            open "$url/setup" 2>/dev/null
        else
            xdg-open "$url/setup" 2>/dev/null
        fi
    }) &

    exec python3 server.py
}
