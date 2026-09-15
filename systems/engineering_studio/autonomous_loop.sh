#!/bin/bash
# Engineering Studio V6 - Continuous Autonomous Operation Loop
# Runs intelligent daemon cycles continuously, persisting evidence

LOG_DIR="${NEXUS_ROOT}/systems/engineering_studio/runtime"
CYCLE_COUNT=0
START_TIME=$(date +%s)

echo "🚀 ENGINEERING STUDIO V6 - AUTONOMOUS PRODUCTION MODE"
echo "Started: $(date)"
echo "Log directory: $LOG_DIR"
echo ""

while true; do
  CYCLE_COUNT=$((CYCLE_COUNT + 1))
  CYCLE_TIME=$(date '+%Y-%m-%d %H:%M:%S')

  # Run autonomy loop
  cd ${NEXUS_ROOT}
  python3 systems/engineering_studio/v6_intelligent_daemon.py >> "$LOG_DIR/autonomous_cycles.log" 2>&1

  # Log cycle completion
  echo "[$CYCLE_TIME] Cycle $CYCLE_COUNT completed" >> "$LOG_DIR/autonomous_operation.log"

  # Update runtime counter
  echo "$CYCLE_COUNT" > "$LOG_DIR/cycle_count.txt"

  # Brief pause between cycles (allows system responsiveness)
  sleep 1

  # Every 10 cycles, report status
  if [ $((CYCLE_COUNT % 10)) -eq 0 ]; then
    RUNTIME=$(($(date +%s) - START_TIME))
    echo "✅ $CYCLE_COUNT cycles completed | Runtime: ${RUNTIME}s | Time: $CYCLE_TIME" >> "$LOG_DIR/autonomous_operation.log"
  fi
done
