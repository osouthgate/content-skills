# Slates — forced choices, never blanks

*Generic procedure — cite "framework § The contract, rule 7" for the rule this
implements; this file does not restate it.*

Two fields in an outcome doc ask the human to choose rather than let a blank stand: the
outcome line and the how-we'll-know signal, both in §0. Both use the same underlying
move — offer verbatim candidates, never a description of a kind of thing — but the two
procedures differ in shape, and one item (the rules block) is permanently exempt from
either.

## The outcome-line slate

1. **Open question first, one turn.** Ask what is true after this ships, in the user's
   own words. One line is enough.
2. **No crisp line back → slate it.** A braindump, a "you tell me," a shrug, or a ticket
   pasted with no framing all count as "no crisp line." Present 3–4 candidate outcome
   lines, each written **verbatim as it would appear in §0** — never as a description of
   a kind of outcome.
3. **Every candidate carries three annotations:**
   - **Selected because —** the source line it derives from: a transcript quote, a
     ticket line, a file:line, or "your words, tightened." A candidate with no
     traceable source is the agent inventing intent — cut it.
   - **Commits you to —** the mechanism it forces and the option it rules out.
   - **Think about —** what it leaves unsaid; the reading under which it is satisfied
     but the user would still be unhappy.
4. **Recommended-first, scored** (architecture § Rules for every file in this skill —
   every choice put to the user). One candidate is marked **(Recommended)** and listed
   first, with one concrete reason. Every candidate — "none of these" included — carries
   a completeness score, 1–10: how fully it captures the outcome as understood so far,
   not how likely it is to be picked.
5. **"None of these — here's mine" is always on offer and never last.** It is a real
   option, not a footnote.
6. **Quote the final text back for confirmation** before it enters §0. If the user edits
   a candidate, **the edit is what enters, not the candidate** — a picked-then-tweaked
   candidate is not the candidate anymore.
7. **No pick → the doc stays `draft`**, with a BLOCKING question logged in §9. Never
   write a placeholder into §0 to keep moving.

**Anchoring is the cost, and it is paid on purpose.** Four candidates define a space,
and the line the user would have written unprompted is often outside it. That is why the
open question comes first, why every candidate must cite a source rather than be
invented to fill a slot, and why the slate stops at the outcome line and the signal — it
does not extend to the rules (below).

## The how-we'll-know slate

1. **One question, one turn.** Unlike the outcome line, this is not staged — ask it
   once, with the candidates already attached.
2. **3–4 candidates, each written verbatim as it would appear in §0** — not a
   description of a kind of signal. Label each with its kind:
   - **(a)** a test that flips red → green
   - **(b)** a demo someone watches
   - **(c)** a number in prod that must hold, at a value
   - **(d)** a claim the team can now make to a customer
3. **Recommended-first, scored** — the same rule as the outcome-line slate: one
   candidate marked **(Recommended)** with one concrete reason, listed first; every
   candidate scored 1–10 on completeness.
4. **Name the anti-pattern in the options list, don't just avoid it.** "The acceptance
   tests pass" duplicates §6 (framework § Acceptance) and decides nothing new — the
   signal in §0 should buy something §6 doesn't. Listing it as a labelled non-example is
   more useful than silently omitting it.
5. **Placeholders are banned.** A blank in the file is indistinguishable from a decision
   at review time, and survives to `agreed`.
6. **No pick → the doc stays `draft`**, with the question logged BLOCKING in §9.

The confirm-and-quote-back rule and the edit-enters-not-the-candidate rule (outcome-line
slate, step 6) apply here exactly as written — there is one confirmation mechanic, used
twice, not two mechanics.

## Once the signal is chosen: re-read the open decisions

The chosen how-we'll-know line can rule an open decision out — framework § Section
rules, "the success signal can rule an open decision." Re-read every OPEN §8/§9
decision against it: an option under which the signal cannot be staged has been ruled
out by the signal itself. Record the narrowing in §8 — the decision, the implication,
and that it followed from the signal — leaving ratification with the human; the agent
records the narrowing, it does not declare the decision closed on its own initiative.

## Rules are never slated

Both slates exist because a blank is worse than an anchored choice. Rules do not get the
same trade: they enter §0 **only by verbatim line-by-line confirmation** — never a
pick-list, never a candidate. Two reasons, not one:

- **The rules block is where a paraphrase is most likely to survive as a
  "confirmation"** (framework § Why this exists). A slate is itself a paraphrase,
  offered as a menu; picking from a menu of paraphrases ratifies whichever paraphrase
  reads closest, not the source.
- **A pickable rule is agent framing with a human signature on it.** The rules block's
  sentences are the human's, not the agent's best guess at the human's — a candidate
  rule the human merely approves is exactly the loop this framework exists to break,
  however good the candidate reads.

A rule that cannot be gotten to verbatim in one pass is a finding, not a reason to make
it pickable: stop, and say the capability is not ready for that rule yet.

## The confirmation sheet: small and staged

A slate produces one decision; a braindump or transcript produces many at once, and the
same discipline applies at volume. Confirm the **~10 most load-bearing lines first** —
one screen. A forty-item sheet does not get answered; it gets skimmed and
rubber-stamped, which is worse than an unconfirmed sheet, because it looks like
confirmation. The rest follows in later passes, not in the first ask.

## A pending sheet never blocks review work

If the user redirects to reviewing, iterating with another agent, or anything else
before answering a confirmation sheet, do that work. The human half stays pending — it
does not get drafted around — but only drafting the **agent** half of a **new** doc
waits on it. Revise, review, merge, arm, intake and reconcile all proceed on whatever is
already confirmed.

## Re-surfacing the open remainder

At the next natural decision point, re-show what is still open — never the full sheet
again, never an item already answered. Compactly: the outstanding line or candidate, one
line each, grouped as "still open" rather than re-narrated. Re-asking an answered item
reads as not having listened; that costs more than the delay in answering ever did.
