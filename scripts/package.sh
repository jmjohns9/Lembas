#!/usr/bin/env bash
# Build dist/lembas.skill and dist/ithildin.skill, the files Claude apps install with "Save skill",
# and dist/SHA256SUMS.
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
# Checksums, published with each release so a download can be checked: sha256sum -c SHA256SUMS
if command -v sha256sum >/dev/null; then sum=(sha256sum); else sum=(shasum -a 256); fi
(cd dist && "${sum[@]}" lembas.skill ithildin.skill > SHA256SUMS)
echo "Wrote dist/SHA256SUMS"
