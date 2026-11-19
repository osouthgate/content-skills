# Turn KEEP into a cleanup decision

Start with the stderr summary, then use the JSON rows to investigate a small,
high-value batch. Each row shows the first blocker encountered. Clearing it
reveals the next check. Group sizes describe the checkouts, and may overlap.
Treat unmeasured sizes as unknown.

Give the user one recommended batch with exact paths, the evidence for keeping
them, the proposed remedy and its cost or tradeoff. Separate candidates that
already have merge proof from candidates that still need it. When the next
step is read-only and within scope, do it before reporting back. Ask for a
decision when the next step modifies retained work or the user reserved it.

| First blocker | Find out and propose |
| --- | --- |
| Recent activity | Identify the largest or oldest relevant candidates. Give the earliest time they can pass the age gate, assuming no activity. When useful, explain and run a narrower read-only report with a lower cutoff to expose later blockers. |
| Git lock | Read the recorded note in `git -C <repo> worktree list --porcelain` or the report. Say when Git recorded no reason. Correlate the path with session records, claims and local activity. A generated agent directory name or absent local process alone cannot establish who owns it or whether it is abandoned. Ask the owner to release a live lock. For a confirmed abandoned lock, propose unlocking the exact path only with authorisation and rerun the report. |
| Live process or keep marker | Identify the owning session where possible and have it finish or release the checkout. Respect deliberate keep markers and removable-media locks. |
| Git operation | Identify the operation from Git status and have its owner finish or cancel it deliberately. |
| Local changes | Inspect Git status and diff summaries. Identify whether the changes are staged, unstaged or untracked. Propose preserving them in a reviewed commit or private backup before revisiting the tree. |
| Protected ignored paths | List path names and sizes. Distinguish known regenerable output from credentials, local databases and unknown files using project documentation and metadata. Propose an exact private archive and verification for anything that needs preserving. Get approval before moving or discarding the listed paths. |
| Open PR or unproven integration | Identify the branch, HEAD and PR state. For GitHub, check whether the exact head was merged into the default branch. A draft, closed unmerged PR or later local commits need a decision about the work before cleanup. |
| Stale or missing origin refs | Compare local tracking refs with the remote default using `git -C <repo> ls-remote --symref origin HEAD`. Recommend the exact repo and ref refresh needed. If the default branch is excluded by the fetch configuration, explain that before proposing changes. |
| Main, bare or unsupported checkout | Exclude from the linked-worktree selection. If most space is here, offer a separate review of recognised caches. |
| Missing path or registration mismatch | Check whether the path was moved, mounted elsewhere or already gone. Report missing registrations separately from disk savings and leave repair or pruning to a separately approved task. |
| Submodules or failed checks | Identify the affected submodule or failing check. Recommend the smallest repair or owner review that restores reliable evidence. |

After the agreed remedy, run a fresh report and prepare a saved plan only for
eligible paths. Keep the existing approval and verification steps.
