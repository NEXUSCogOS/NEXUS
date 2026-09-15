#!/usr/bin/env bash
set -euo pipefail
BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$BIN/.." && pwd)"
echo "=== PUBLICATION SELF TEST ==="
for f in \
 "$ROOT/00_GOVERNANCE/MASTER_DIRECTIVE.md" \
 "$ROOT/00_GOVERNANCE/publication_policy.json" \
 "$ROOT/01_REGISTRY/repositories.json" \
 "$ROOT/08_SCHEMAS/release_manifest.schema.json"; do
 [[ -f "$f" ]] || { echo "FAIL missing $f"; exit 1; }
done
python3 -m json.tool "$ROOT/01_REGISTRY/repositories.json" >/dev/null
python3 -m json.tool "$ROOT/00_GOVERNANCE/publication_policy.json" >/dev/null
count=$(find "$ROOT/02_PUBLIC_REPOS" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
[[ "$count" = "4" ]] || { echo "FAIL expected 4 repo skeletons, got $count"; exit 1; }
echo "PASS: publication subsystem structure valid"
echo "PASS: no remote publication action exists in this installer"
