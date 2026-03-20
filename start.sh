#!/bin/bash
# start.sh — Launch the Plant Precis Producer web interface.
# Opens the browser and starts the server. Exits when you close the terminal.

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/install_steps.sh"

step_launch
