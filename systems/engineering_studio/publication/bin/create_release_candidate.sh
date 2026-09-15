#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 ]] || { echo "Usage: $0 <repository-name>"; exit 2; }
REPO="$1"
BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$BIN/.." && pwd)"
SRC="$ROOT/02_PUBLIC_REPOS/$REPO"
[[ -d "$SRC" ]] || { echo "Unknown repository: $REPO"; exit 2; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$ROOT/03_RELEASE_CANDIDATES/${REPO}_${STAMP}"
mkdir -p "$DEST"
cp -R "$SRC/." "$DEST/"
REPORT="$ROOT/06_AUDITS/${REPO}_${STAMP}_scan.json"
set +e
python3 "$BIN/scan_candidate.py" "$DEST" --output "$REPORT"
SCAN=$?
set -e
cat > "$DEST/RELEASE_MANIFEST.json" <<EOF
{
  "repository": "$REPO",
  "created_at": "$STAMP",
  "source_refs": [],
  "claim_ids": [],
  "evidence_ids": [],
  "approval_state": "NOT_REVIEWED",
  "gates": {
    "secret_scan_exit": $SCAN,
    "human_approval": false
  }
}
EOF
echo "Candidate: $DEST"
echo "Audit: $REPORT"
echo "NOT PUBLISHED. Human review/approval still required."
[[ "$SCAN" -eq 0 ]] || exit "$SCAN"
