#!/usr/bin/env bash
# Build dist/lembas.skill, the file Claude apps install with "Save skill".
# The archive contains lembas/SKILL.md, the squeeze compressor and the optional hook.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/lembas.skill
(cd skills && zip -q -r ../dist/lembas.skill lembas -x '*.DS_Store' '*__pycache__*')
echo "Built dist/lembas.skill"
unzip -l dist/lembas.skill
