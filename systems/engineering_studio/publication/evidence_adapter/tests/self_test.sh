#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
cd "$(dirname "${BASH_SOURCE[0]}")/.."
pwd
)"

echo "=== EVIDENCE ADAPTER SELF TEST ==="

for f in \
 "$ROOT/config/source_policy.json" \
 "$ROOT/registry/public_artifacts.json" \
 "$ROOT/registry/dependencies.json" \
 "$ROOT/registry/claim_evidence_map.json" \
 "$ROOT/bin/check_staleness.py" \
 "$ROOT/bin/check_release_eligibility.py"
do

    test -f "$f" || {
        echo "FAIL: missing $f"
        exit 1
    }

done


python3 -m json.tool \
 "$ROOT/config/source_policy.json" \
 >/dev/null

python3 -m json.tool \
 "$ROOT/registry/public_artifacts.json" \
 >/dev/null

python3 -m json.tool \
 "$ROOT/registry/dependencies.json" \
 >/dev/null

python3 -m json.tool \
 "$ROOT/registry/claim_evidence_map.json" \
 >/dev/null


python3 \
 "$ROOT/bin/check_staleness.py" \
 --registry \
 "$ROOT/registry/public_artifacts.json" \
 --output \
 "$ROOT/reports/staleness_test.json"


python3 \
 "$ROOT/bin/check_release_eligibility.py" \
 --claim-map \
 "$ROOT/registry/claim_evidence_map.json" \
 --output \
 "$ROOT/reports/eligibility_test.json"


echo "PASS: evidence adapter operational"
