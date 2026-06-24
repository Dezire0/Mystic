#!/usr/bin/env bash
set -euo pipefail

python -m mystic.cli.main init
python -m mystic.cli.main run "Attack the Erdos-Straus conjecture: for every integer n >= 2, prove or refute that 4/n = 1/x + 1/y + 1/z for positive integers x,y,z."

