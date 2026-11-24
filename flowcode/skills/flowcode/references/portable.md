# flowcode: portable route

For any host that is not Claude Code with the `Workflow` or `Agent` tool: Codex, Cursor, Antigravity, a plain chat model. Your host's own rules and tools take priority over this file. This is a procedure, not a program. There is nothing to run, and you must not make up a launcher for it.

The method is the same as on Claude Code: **look, build, review**. Each stage uses the cheapest model that can do it, and a separate reviewer checks the result at the end.

Throughout, `<run>` means `.workflow/flowcode/<slug>/`, the scratch folder for this task.

## 1. Size the task

Note one line for each:

- **kind**: research, bug fix, feature, refactor, migration, audit, docs
- **risk**: low, medium, high
- **reach**: one file, one module, whole repo, something outside the repo
- **proof**: which command, test, build or manual check will show it works

Then choose a mode.

| Mode | Choose it when | What you do |
| --- | --- | --- |
| Solo | The task is small and clear | Just do it. No files. Run the smallest check that proves it. |
| Sequential | The task has phases or real unknowns, or your host cannot spawn agents | Write a plan, then work through the tasks yourself, one pass each (section 5). |
| Parallel | Several tasks are independent and your host can spawn agents | Spawn agents using the host's own feature (section 4). |

If you are unsure whether your host can spawn agents, assume it cannot, use Sequential, and say so in one line.

## 2. Pick a model per stage

| Stage | Work | Tier |
| --- | --- | --- |
| Look | search, list files, trace code, read tests, run the suite | smallest and fastest |
| Build | write the change and its tests inside files you own | middle |
| Review | check the change against the task | strongest you have |

Tiers are not model ids. Use only names or ids your host actually lists. If your host accepts a fixed list of ids, pick from that list. If you cannot tell which entry is the right tier, do not guess: use the host's default model for that stage and tell the user which stages ran on it. Running every stage on one model is acceptable. Making the review independent is not optional (section 6).

## 3. Write the plan

Before any edits, record a baseline: the current commit (`git rev-parse HEAD`) and `git status --porcelain`. Anything already dirty is not part of this task.

For Sequential and Parallel modes, write a short plan to `<run>/plan.md`. If the workspace does not allow new files, keep the plan in your reply and use that copy wherever these instructions say "the plan". `<run>` is scratch: suggest to the user that they ignore `.workflow/`, but do not edit `.gitignore` or any other tracked file for it. Cover:

- the goal and what "done" looks like
- limits, and any action from section 8 that applies
- the tasks: for each, a number, its scope, whether it is read-only or edits files, which files it owns, and its stage (look, build or review)
- how you will check the result

Templates are in [packets.md](packets.md).

A good task is narrow and ends in something checkable: "trace how a request reaches the database", "add input validation in these three files", "write tests for the parser". A poor task is open-ended: "sort out the module", "make it work", "change whatever is needed". Two edit tasks must never own the same file.

## 4. Parallel mode

Only when the host gives you a way to start agents (Codex `spawn_agent`, Cursor `Task` sub-agents, Antigravity agents, or similar). Use that feature. Do not start agents through shell scripts or subprocesses you invent.

- Do the step you are blocked on yourself. Hand out only side work that can proceed at the same time.
- Two or three agents is usually enough. Ask the user before running more than six at once.
- One build round and one review round, plus the single fix round and its re-check from section 6. Anything beyond that needs the user's approval.
- Agents that only read can run freely. Agents that edit need file ownership that does not overlap.
- Keep every edit in the main checkout. Do not use agent types that work in their own worktree or branch (for example Cursor's `best-of-n-runner`), unless you merge their result back before the review. Otherwise the review sees an empty change.
- Tell every editing agent that other agents are changing the repo at the same time, and that it must leave changes it did not make alone and work around them. If it needs a file it does not own, it stops and reports the dependency. It does not edit that file.
- After starting agents, carry on with your own work. Wait only when you cannot continue without a result.
- If the host forbids spawning agents without a particular phrase, or blocks it, switch to Sequential and say so in one line.

## 5. Sequential mode

Work through the tasks in order: every look task, then every build task, then the review. After each task, write down what you found with proof (file paths, line numbers, command output) in `<run>/notes/<number>-<slug>.md`, or a paragraph in your reply if you cannot write files. Do not rely on a conclusion that has no proof attached.

## 6. Review

Always review in Sequential and Parallel modes. This is the step that earns the whole approach.

**Make it independent.**
- With agents available, spawn a new agent for the review and start it with **no inherited conversation history**. Many hosts copy the parent's history by default (Codex `spawn_agent` does, unless you set `fork_turns` to `"none"`). Turn that off, or the reviewer will see the builders' reasoning and tend to agree with it.
- With no agents (Sequential mode), you cannot drop your own context. Reread the plan, then reread every changed file from disk as if you had not written it, and judge only what is there. For a risky change, tell the user to open a fresh session and paste the reviewer brief from [packets.md](packets.md).

**Give it the real change, and only this task's change.**
- Work out the list of files this task changed or created, from the baseline in section 3. Do not include files that were already dirty, and do not include scratch files under `<run>`.
- Give the reviewer the original task, that file list, and the content of the change: `git diff HEAD -- <files>` (this covers staged and unstaged edits), plus the full text of any new file on the list.
- Also tell the reviewer to run `git status --porcelain` and flag any file that changed but is not on the list. It must not open secrets such as `.env` files, keys or credentials, even if they appear as untracked.
- Do not give it the builders' own summaries.

**What to ask for.** Problems ranked by severity, each with a file and line and a case where it breaks. Ask it to check for wrong behaviour, requirements that were missed, missing tests and unsafe operations. If it finds nothing, it should say so and list what it checked.

**One fix round.** In Parallel mode, pass real problems back to the builders. In Sequential mode, fix them yourself. Then have the reviewer look only at what changed. Ask the user before doing more.

## 7. Take it home

You, not the agents, are responsible for the result.

- Read every note. Compare the files agents say they changed with the actual diff.
- When agents disagree, decide from the code, the tests or the docs, not from whoever sounds more certain.
- Discard claims that come without proof.
- Choose checks by risk. Low: read the diff and run one targeted test. Medium: targeted tests plus typecheck or lint. High: the full test suite, a build, a smoke run and the independent review.
- Record each check as `passed`, `failed`, or `not run` with the reason.

## 8. Stop and ask first

Before any of these, ask the user one clear question, and until they answer do only read-only work or local drafts:

- deleting, overwriting, renaming in bulk, or force pushing
- publishing, deploying, sending email or posting anywhere
- touching production data, credentials, secrets, billing or accounts
- repo-wide rewrites
- editing files that are not part of the task, such as `.gitignore`
- starting an unusually large or long-running set of agents

Do not commit, push, publish or deploy unless the user asked for it.

## 9. Report

Keep it short: what was achieved, which files changed, which checks ran and their result, which checks were not run and why, and what risk remains. Do not paste agent logs.
