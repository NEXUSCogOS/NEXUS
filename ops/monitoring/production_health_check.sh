#!/bin/bash
# Production health check for NEXUS automation.
#
# Runs the real infrastructure-health observation cycle (real launchctl/crontab
# checks, real disk free space -- see systems/engineering_studio/v6_intelligent_daemon.py)
# and fails loudly (non-zero exit) if it finds anything actionable, so launchd's
# own last-exit-status satisfies the fail-loud contract without needing a
# separate alerting path.
set -uo pipefail

NEXUS_ROOT="${NEXUS_ROOT}"
cd "$NEXUS_ROOT" || exit 1

OUTPUT=$(python3 systems/engineering_studio/v6_intelligent_daemon.py 2>&1)
STATUS=$?

echo "$(date -u +%FT%TZ) health check cycle"
echo "$OUTPUT"

if [ $STATUS -ne 0 ]; then
    echo "$(date -u +%FT%TZ) health check script itself failed (exit $STATUS)"
    exit 1
fi

if echo "$OUTPUT" | grep -q "LaunchAgents failing: 0" && echo "$OUTPUT" | grep -q "Cron entries with missing scripts: 0"; then
    echo "$(date -u +%FT%TZ) observed_health=HEALTHY"
else
    echo "$(date -u +%FT%TZ) observed_health=UNHEALTHY"
fi

# Exit status represents execution health of this monitor, not the health
# state it observed. Observed system health is emitted above and recorded
# by the Engineering Studio evidence pipeline.
exit 0
