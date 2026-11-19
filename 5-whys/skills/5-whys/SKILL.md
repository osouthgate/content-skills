---
name: 5-whys
description: Trace a problem to a root cause with Five Whys. Use when the user asks to find the root cause, why this happened, why it keeps coming back, debug a failure, or separate a symptom from the cause that would prevent recurrence.
argument-hint: "[problem]"
---

# 5 Whys

Five Whys is one root-cause technique: ask why, follow the answer, and stop at a
cause whose removal would prevent the problem coming back. It is a short cause
chain, not a full root-cause analysis. ISO/IEC 31010 also lists fault trees,
FMEA, Ishikawa diagrams, and Pareto analysis. Use those, or say they are still
needed, when the event is a safety incident, an accident, or a system whose
defenses failed independently of one another.

A **root cause** is a factor whose removal prevents recurrence. A **causal
factor** contributes to the outcome, but removing it does not certainly prevent
recurrence. There can be more than one root cause. Five is a habit, not a
quota: stop at three, or continue past five, when the evidence says so.

## Steps

1. **State the problem as something observed.** What happened, when, where, and
   what the impact was. "The system is slow" is not a problem statement.
   "Checkout p95 went from 50ms to 500ms at 14:10" is.
2. **Timeline.** From the last known-good state to the failure. Mark each item
   as evidenced or inferred. Missing evidence ends that branch; do not fill the
   gap with a plausible cause.
3. **Ask why, one step at a time.** Each answer must explain the step above it
   and cite the evidence (log, metric, code, change, witness). If two causes
   are both live, branch. Do not collapse them into one story.
4. **Apply the removal test.** If removing this factor would prevent the
   problem recurring, it is a root-cause candidate. If it only softens the
   outcome, it is a causal factor. Stop a branch when the next why is not
   actionable, or sits outside what this investigation can change.
5. **Walk the chain backwards.** If the candidate is removed, each earlier step
   does not happen, and the problem does not occur. A link that fails this test
   is not the cause of the step above it.
6. **Countermeasures, only for causes you can act on.**
   - Immediate: stop the current harm.
   - Preventive: removing or redesigning this stops recurrence. Prefer removing
     the cause over adding a checklist or more training.
   - Detection: how you would notice if prevention fails.
   If the cure costs more than the problem, say so and leave the choice open.

Do not stop at a person ("someone made a mistake"). Ask what in the system let
that action through: a missing check, a missing test, a design that requires a
perfect operator.

## Output

```markdown
## 5 Whys: [title]

### Problem
What / when / where / impact.

### Timeline
- [time] evidenced: …
- [time] inferred: …

### Chain
1. Why …? → … (evidence)
2. Why …? → … (evidence)
   - branch, if a second cause is live

### Causes
- Root cause: … — removing it prevents recurrence because …
- Causal factor: … — it contributed; removing it does not certainly prevent recurrence

### Backward check
Removing [root] stops [previous step], which stops [problem]. Broken links: …

### Countermeasures
- Immediate: …
- Preventive: …
- Detection: …

### Unknown
What is still missing, and which branch stopped because of it.
```

## Limits

- Do not invent a cause to finish a chain of five.
- Do not present this chain as a complete investigation of a safety event.
- In software, observation is often incomplete. "No single root cause is
  evidenced" is a valid result. Name the last evidenced cause and the missing
  observation.
