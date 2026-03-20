#!/bin/bash
# start.sh — Launch the Plant Precis Producer web interface.
# Opens the browser and starts the server. Exits when you close the terminal.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

PORT=7734
URL="http://localhost:$PORT"

# Check dependencies
python3 -c "import fastapi, uvicorn" 2>/dev/null || {
    echo "Installing FastAPI and uvicorn..."
    pip3 install fastapi uvicorn
}

echo ""
echo "  Plant Precis Producer"
echo "  $URL"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

# Open browser after a short delay (server needs a moment to start)
(sleep 1 && open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null) &

# Start server (blocks until Ctrl+C)
exec python3 server.py
