---
title: {{TITLE}}
slug: {{SLUG}}
status: {{STATUS}}            # backlog | toDo | in_progress | done (mirrors the folder)
created: {{DATE}}
ticket: {{TICKET}}           # LOA-XXX or —
design: {{DESIGN_STATE}}     # docs/designs/X.md | exempt — <reason>
acceptance: {{ACC_STATE}}    # required | exempt — <reason>
spec_sha: {{SPEC_SHA}}       # sha of the red-test commit (— if acceptance exempt)
sealed_paths:                # test/eval files the build may NOT edit
  - {{SEALED_PATH}}
---

# Plan: {{TITLE}}

> Routing row: {{ROUTING_ROW}}   <!-- delta | implementation | from-design | exempt -->

## Grounding

- **Design:** {{DESIGN_LINK}} ({{DESIGN_STATE}})
- **How-to:** {{HOWTO_LINK}} ({{HOWTO_STATE}})   <!-- exists | owed-on-ship -->
- **Related plans:** {{RELATED_PLANS}}
- **Conforms to pattern:** {{PATTERN}}            <!-- named pattern from the how-to -->
- **Code touchpoints:** {{TOUCHPOINTS}}
- **Ticket:** {{TICKET}}

## Goal

{{ONE_PARAGRAPH_GOAL}}

## Non-goals

- {{NON_GOAL}}

## Phases

Small, verifiable, ordered. Each phase names the acceptance command(s) it turns green.

1. **{{PHASE_TITLE}}** — {{PHASE_DESC}}  → turns green: `{{PHASE_GREENS}}`
2. ...

## Risks

1. **{{RISK}}** — mitigation: {{MITIGATION}}

## Acceptance

acceptance: {{ACC_STATE}}
spec_sha: {{SPEC_SHA}}
sealed_paths:
  - {{SEALED_PATH}}

<!-- RED now → GREEN at done. Threshold/golden-set for eval-shaped work, never exact orderings. -->

- [ ] {{ACCEPTANCE_COMMAND}}        # RED now ({{RED_STATE}}) → GREEN at done

### Red proof

```
{{PASTE_RED_TEST_OUTPUT}}
```

## How-to debt

{{HOWTO_DEBT}}   <!-- if how-to is owed-on-ship, name the guide to write when this lands -->
