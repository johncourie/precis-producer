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
_is_windows() { [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == MSYS* ]] || [[ "$(uname -s)" == CYGWIN* ]]; }

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
    elif _is_windows; then
        _err "Automatic poppler install is not supported on Windows."
        echo "  Install poppler using one of:"
        echo "    scoop install poppler"
        echo "    conda install -c conda-forge poppler"
        echo "  Or download from: https://github.com/oschwartz10612/poppler-windows/releases"
        return 1
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
        local zotero_db=""
        if [[ -f "$HOME/Zotero/zotero.sqlite" ]]; then
            zotero_db="$HOME/Zotero/zotero.sqlite"
        elif [[ -f "$HOME/.var/app/org.zotero.Zotero/data/zotero/zotero.sqlite" ]]; then
            zotero_db="$HOME/.var/app/org.zotero.Zotero/data/zotero/zotero.sqlite"
        elif [[ -n "${APPDATA:-}" ]] && [[ -f "$APPDATA/Zotero/Zotero/zotero.sqlite" ]]; then
            zotero_db="$APPDATA/Zotero/Zotero/zotero.sqlite"
        fi
        if [[ -n "$zotero_db" ]]; then
            local zotero_dir
            zotero_dir="$(dirname "$zotero_db")"
            python3 -c "
import json, sys
db_path, storage_path = sys.argv[1], sys.argv[2]
c = json.load(open('config.example.json'))
c['zotero']['enabled'] = True
c['zotero']['db_path'] = db_path
c['zotero']['storage_path'] = storage_path + '/storage'
json.dump(c, open('config.json','w'), indent=2)
" "$zotero_db" "$zotero_dir"
            _ok "config.json created (Zotero detected at $zotero_db)"
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

    _info "Starting Plant Precis Producer..."
    exec python3 start.py
}
