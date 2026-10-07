#!/usr/bin/env bash
# Build dist/lembas.skill, the file Claude apps install with "Save skill".
# The archive contains only lembas/SKILL.md.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/lembas.skill
(cd skills && zip -q -r ../dist/lembas.skill lembas -x '*.DS_Store')
echo "Built dist/lembas.skill"
unzip -l dist/lembas.skill
