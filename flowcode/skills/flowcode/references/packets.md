# flowcode: templates

Open this from [portable.md](portable.md) when you write the plan or brief an agent. Keep every file short and drop any field that has nothing to say.

## Folder layout

Use `.workflow/flowcode/` unless the project's own instructions name a different scratch folder.

```text
.workflow/flowcode/<slug>/
  plan.md
  tasks/01-<slug>.md
  notes/01-<slug>.md
  review.md
  report.md
```

`<slug>` is lowercase with hyphens, under 64 characters. Task and note files start with a two-digit number in the order they run.

## plan.md

```text
Goal:
Done when:
Mode: solo | sequential | parallel   (if not parallel, say why)
Risk: low | medium | high
Limits and stop-and-ask items:
Tasks:
- 01 <name>   stage: look | build | review   read-only | edits   owns: <files>
How we will check:
```

## Task

```text
Task 01: <name>
Stage: look | build | review
Access: read-only | edits
Owns: <files or module; "none" if read-only>
Do: <one specific objective>
Start from: <paths, earlier notes>
Return: <what the answer must contain>
```

## Note

```text
Task 01 note
State: finished | stuck | partly done
What was found or done:
Proof: <file:line, command output>
Files changed: <list, or none>
Open risks or blockers:
```

## Brief for an agent that only reads

```text
You are working in the repo at <absolute path>. Other agents may be working in it too.

Your job:
<one specific read-only objective>

How:
- read the sources listed here, plus one nearby hop if needed
- cite file paths and line numbers
- keep findings short and back each with proof

Off limits:
- changing any file
- destructive commands
- redoing another task's work

Return: what you found, the proof, any risks, and what to do next.
```

## Brief for an agent that edits

```text
Other agents are changing this repo at the same time as you. Leave changes you did not make alone, and work around them.

Repo: <absolute path>
Files you own: <files or module>

Your job:
<one specific implementation objective>

How:
- change only the files you own
- if you need a change in a file you do not own, stop and report what you need and why; do not edit it
- add or update focused tests when the area has them
- finish by listing every file you touched

Off limits:
- altering behaviour outside this task
- reformatting files you do not own
- commit, push, publish or deploy

Return: files changed, what you did, the checks you ran, and any risks or blockers.
```

## Brief for the reviewer

```text
You are reviewing a change you did not write.

The original request:
<paste the user's request>

Files this task changed or created: <list of paths>

Read the real changes in <absolute path>, not anyone's description of them. Run `git diff HEAD -- <those paths>` (staged and unstaged edits) and read the full text of any new file on the list, because new files do not show in a diff. Also run `git status --porcelain` and flag any changed file that is not on the list. Never open `.env` files, keys or credentials.

List problems from most to least serious. For each give the file and line, what is wrong, and a concrete case where it breaks. Check for wrong behaviour, missed requirements, missing tests and unsafe operations. Leave out style opinions.

If you find nothing, say "no problems found" and list what you checked.
Do not change any file.
```

## report.md

```text
Achieved:
Files changed or created:
Checks: <each one: passed | failed | not run (reason)>
Review: <problems found, what was fixed, what was left and why>
Risk remaining:
```
