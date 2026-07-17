#!/bin/bash
# Docker Hub Pull 数追踪脚本 (Linux/macOS)
# 用法: ./track-pulls.sh [--history] [--csv]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/track-pulls.py" "$@"
