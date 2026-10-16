#!/usr/bin/env bash
# Build dist/lembas.skill and dist/ithildin.skill, the files Claude apps install with "Save skill".
# Each archive holds one skill folder: its SKILL.md and its scripts.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
for skill in lembas ithildin; do
  rm -f "dist/$skill.skill"
  (cd skills && zip -q -r "../dist/$skill.skill" "$skill" -x '*.DS_Store' '*__pycache__*')
  echo "Built dist/$skill.skill"
  unzip -l "dist/$skill.skill"
done
