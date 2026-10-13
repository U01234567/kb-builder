#!/bin/bash
# start_kb-builder for Linux: bash start_kb-builder_Linux.sh
# Finds Python 3.12 or newer, then runs scripts/start.py: updates, packages, and with NVIDIA GPUs the Ollama release.
# Built around our university's setup; adapt it freely to yours (see scripts/start.py).
cd "$(dirname "$0")" || exit 1
for python in python3 python3.14 python3.13 python3.12 "$HOME/miniforge3/bin/python3"; do
    if command -v "$python" >/dev/null 2>&1 && "$python" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
        exec "$python" scripts/start.py
    fi
done
echo "Python 3.12 or newer was not found."
echo "Install it (on a server without administrator rights, Miniforge in your home folder works), then run this again."
exit 1
