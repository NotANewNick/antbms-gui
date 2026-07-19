#!/usr/bin/env bash
# Launcher for the ANT BMS desktop GUI.
#
#   ./run_gui.sh                     # open the GUI
#   ./run_gui.sh --demo              # simulated battery
#   ./run_gui.sh --fullscreen --address AA:BB:CC:DD:EE:FF
#
# All arguments are passed through to `python -m antbms_tool gui`.
#
# On first run this creates a virtualenv (default ~/.antbms-venv, override
# with the ANTBMS_VENV environment variable) and installs bleak into it, so
# it works out of the box on Raspberry Pi OS Bookworm where system-wide
# `pip install` is blocked.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # .../antbms_tool
PARENT_DIR="$(dirname "$SCRIPT_DIR")"                        # dir containing the package
VENV="${ANTBMS_VENV:-$HOME/.antbms-venv}"

# `python -m antbms_tool` requires the package folder to have exactly that
# name — catch the classic "copied the contents, not the folder" mistake.
if [ "$(basename "$SCRIPT_DIR")" != "antbms_tool" ]; then
    echo "error: this script must live inside a folder named 'antbms_tool'" >&2
    echo "       (it is in: $SCRIPT_DIR)" >&2
    echo "       Fix:  mkdir antbms_tool && mv the tool's files into it." >&2
    exit 1
fi

if [ ! -x "$VENV/bin/python" ]; then
    echo "First run: creating virtualenv at $VENV ..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

cd "$PARENT_DIR"
exec "$VENV/bin/python" -m antbms_tool gui "$@"
