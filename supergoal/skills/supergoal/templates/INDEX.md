# Supergoal plans — signpost

Index of every Supergoal plan in this repo, one row per plan. **Stage 0 reads this first** to
decide whether to resume an existing plan or start a new one. Each plan's own
`plans/<slug>/STATE.md` is authoritative if a row here looks stale — reconcile on read.

| Slug | Title | Status | Phases | Baseline ref | Updated |
|------|-------|--------|--------|--------------|---------|
| {{SLUG}} | {{TASK_TITLE}} | PLANNING | {{N}} | {{BASELINE_SHA}} | {{DATE}} |

<!--
Status lifecycle: PLANNING → READY_TO_DISPATCH → IN_PROGRESS → COMPLETE   (BLOCKED is a side state)
- PLANNING          plan being written or revised (Stages 1–6)
- READY_TO_DISPATCH goal_prompt.md written; awaiting the user's paste (Stage 7)
- IN_PROGRESS       the /goal run is executing phases
- BLOCKED           a phase or the audit hit a 3-strike handoff; needs the user
- COMPLETE          audit passed, SUPERGOAL_RUN_COMPLETE printed

Resume eligibility (Stage 0): READY_TO_DISPATCH, IN_PROGRESS, and BLOCKED rows are offered for
resume; PLANNING and COMPLETE are not. Baseline ref is the plan-commit SHA captured at dispatch
(Stage 7) — Stage 0 compares it against `git rev-parse HEAD` to detect a stale dispatch line.
Add one row per plan; never delete rows (COMPLETE plans are the run history / audit trail).
-->
