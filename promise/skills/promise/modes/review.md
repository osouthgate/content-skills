Read before this: references/anti-rationalizations.md · outcome-framework.md § The framework as a review rubric · § Section rules
Phase 0 line: mode `review` (say if inferred), framework source (the rubric's authority), docs home and its source, whether a map is configured, and whether the project is adopted.
Writes: nothing in the repo, unless the user asks for a file copy. Findings are delivered inline in chat.

# Review — a doc authored elsewhere

The framework doubles as a review rubric — framework § The framework as a
review rubric is the authority; run it from the section, not from memory.

1. **Read 100% of the source** — chunked if large. State what fraction you
   read if you couldn't finish. Never review a skim. A URL is readable only
   when the session has a fetch tool; otherwise ask for a paste. Never review
   from memory of what a page probably says.
2. **Verify before critiquing.** Spot-check every load-bearing
   current-state claim against live code, with file:line. Three outcome
   classes, all valuable: confirmed (say so — it builds the doc's
   credibility), wrong (invented identifiers, stale claims), and
   **understated** — the code is worse than the doc admits. The sharpest
   findings are usually here.
3. **Run the rubric.** If the target is a file, also run `python3
   "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc>` and fold its
   findings in as the shape half of the rubric. The lint checks shape
   mechanically; it cannot check depth — invariants argued with mechanism
   and boundary, evidence pinned to a commit, design-vs-description
   flagged, alternatives rejected with receipts. That half stays yours to
   judge, against the framework section, not memory of it.
4. **On a re-review, diff against the prior revision** for the three
   erosion classes — framework § The framework as a review rubric: an OPEN
   decision silently asserted; §0 membership changed without confirmation;
   operational content deleted with no stated home. Credit what improved,
   and verify any NEW claims the revision introduced — revisions add claims
   too.
5. **Judge pushback on its merits.** If the doc's author rejected earlier
   feedback with an argument, engage the argument — accept it, or counter
   with a better mechanism. Don't re-assert.
6. **Deliver findings inline in chat**, as a numbered, paste-ready fenced
   markdown block, most severe first, each item actionable by the other
   agent without this conversation. Files can be unreachable across app
   boundaries — inline is the contract; a file copy is optional extra.
7. **Track convergence.** When the doc approaches framework shape, say what
   separates it from `agreed` — usually the human half — and offer to close
   it via the pending interview rather than another review round.
