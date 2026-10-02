#!/usr/bin/env bash
# Run straight from the checkout (no install). Pass --demo for offline sample data.
cd "$(dirname "$(readlink -f "$0")")" && exec python3 -m cachy_widget "$@"
