#!/bin/zsh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

export PYTHONPATH="$HOME/NEXUS/systems/engineering_studio"

python3 "$HERE/controller.py"
