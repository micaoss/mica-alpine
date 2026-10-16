#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
for script in scripts/*.sh; do bash -n "$script"; done
for script in rootfs/usr/local/sbin/*; do sh -n "$script"; done
for script in tests/*.sh; do sh -n "$script"; done
for script in scripts/*.py tests/*.py; do
    [[ -e $script ]] || continue
    python3 - "$script" <<'PY'
import ast
import pathlib
import sys
ast.parse(pathlib.Path(sys.argv[1]).read_text())
PY
done
echo 'PASS: shell and Python syntax'
