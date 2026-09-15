#!/bin/bash
set -euo pipefail

ROOT="$HOME/NEXUS"
ES="$ROOT/systems/engineering_studio"
ORCH="$ES/post_review_orchestrator"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN="$ORCH/results/POST_REVIEW_${TS}"

mkdir -p "$RUN"

echo "======================================================"
echo " NEXUS EV POST-REVIEW ORCHESTRATOR"
echo "======================================================"
echo
echo "This controller is intentionally dormant until"
echo "all required human gate records exist and validate."
echo

set +e
PYTHONPATH="$ES" \
python3 "$ORCH/bin/preflight.py" \
> "$RUN/PREFLIGHT.json"

RC=$?
set -e

cat "$RUN/PREFLIGHT.json"

if [ "$RC" -eq 10 ]; then

    cat > "$RUN/STATUS.txt" <<EOF
STATUS=HUMAN_REVIEW_PENDING
REGISTRY_TRANSITION=NONE
EXPERIMENT_EXECUTION=NONE
EXP006_EXECUTION=NONE
GITHUB_ACTION=NONE
EOF

    echo
    echo "======================================================"
    echo " EXPECTED SAFE STOP"
    echo "======================================================"
    echo "STATUS=HUMAN_REVIEW_PENDING"
    echo "REGISTRY_TRANSITION=NONE"
    echo "EXPERIMENT_EXECUTION=NONE"
    echo "GITHUB_ACTION=NONE"
    echo "REPORT=$RUN"
    exit 0
fi

if [ "$RC" -ne 0 ]; then
    echo "FAIL-CLOSED: PREFLIGHT ERROR RC=$RC"
    exit "$RC"
fi

cat > "$RUN/STATUS.txt" <<EOF
STATUS=POST_REVIEW_ELIGIBLE
NEXT_ACTION=GOVERNED_REGISTRY_TRANSITION
REGISTRY_TRANSITION=NOT_PERFORMED
EXPERIMENT_EXECUTION=NONE
EXP006_EXECUTION=NONE
GITHUB_ACTION=NONE
EOF

echo
echo "======================================================"
echo " POST-REVIEW ELIGIBILITY REACHED"
echo "======================================================"
echo
echo "STOPPING BEFORE REGISTRY TRANSITION."
echo
echo "NEXT_ACTION=GOVERNED_REGISTRY_TRANSITION"
echo "REGISTRY_TRANSITION=NOT_PERFORMED"
echo "EXPERIMENT_EXECUTION=NONE"
echo "EXP006_EXECUTION=NONE"
echo "GITHUB_ACTION=NONE"
echo "REPORT=$RUN"
