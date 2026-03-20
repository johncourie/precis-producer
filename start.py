#!/usr/bin/env python3
"""
start.py — Cross-platform launcher for Plant Precis Producer.

Opens the browser after a short delay, then starts the server.
Works on macOS, Linux, and Windows without any shell dependencies.
"""

import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

PORT = 7734
URL = f"http://localhost:{PORT}/setup"


def open_browser():
    """Open the browser after a short delay to let the server start."""
    import time
    time.sleep(1.5)
    webbrowser.open(URL)


def main():
    server_path = Path(__file__).parent / "server.py"

    print(f"Plant Precis Producer — {URL}")

    # Open browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Replace this process with the server
    # Use subprocess so it works consistently across platforms
    try:
        sys.exit(subprocess.call([sys.executable, str(server_path)]))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
