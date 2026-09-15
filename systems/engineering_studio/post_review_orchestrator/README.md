# NEXUS EV Post-Review Orchestrator

Purpose:

Prepare the post-independent-review execution path without bypassing
human governance.

Current behaviour:

1. Validate every existing formal gate record.
2. Recalculate readiness.
3. Detect whether EXP-001 through EXP-005 remain blocked.
4. Stop safely while human review is pending.
5. Once all required gates legitimately exist, report
   POST_REVIEW_ELIGIBLE.
6. STOP before registry transition.
7. Perform no experiment execution.
8. Keep EXP-006 untouched.
9. Perform no GitHub action.

This controller does not fabricate attestations.
