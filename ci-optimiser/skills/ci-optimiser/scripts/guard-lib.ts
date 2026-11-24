/**
 * Guards that turn the skill's "never trade proof for speed" rule into checks.
 * The pure half of `diff-guard.ts`; plain Node, no installs, no imports.
 *
 *   1. `scanDiff`: reads a change's ADDED lines for the ways a pipeline gets faster
 *      by hiding a failure (retries, skips, `continue-on-error`, `|| true`, wider
 *      timeouts, a bypassed hook, a widened trust boundary), and lists any removed
 *      assertion for a person.
 *   2. `compareTests`: reads JUnit XML from before and after and names every test
 *      that stopped running, was newly skipped, or newly fails. Speed alone cannot
 *      tell a fix from a deletion; names can.
 *
 * Credit: the list of added-line cheats and the `|| true` rule follow the ideas in
 * usejog/joggernaut `evals/lib/cheats.py` (MIT). The code here is written fresh.
 */

export interface FileChange {
  file: string;
  added: string[];
  removed: string[];
}

export interface Finding {
  /** "cheat" fails the guard. "review" is listed for a person and does not fail it. */
  kind: "cheat" | "review";
  file: string;
  what: string;
  line: string;
}

/** Files whose added text is prose or data, not behaviour. */
const SKIP_FILE = /\.(md|txt|jsonl|json|csv|svg|lock)$|(^|\/)(docs\/ledger|test-results|\.joggernaut)\//;

/** One unified diff (`git diff --unified=0`) as the added and removed lines of each file. */
export function parseDiff(diff: string): FileChange[] {
  const out: FileChange[] = [];
  let cur: FileChange | null = null;
  for (const line of diff.split("\n")) {
    if (line.startsWith("+++ ")) {
      const path = line.slice(4).trim();
      cur = { file: path === "/dev/null" ? "" : path.replace(/^b\//, ""), added: [], removed: [] };
      out.push(cur);
    } else if (line.startsWith("--- ")) {
      continue;
    } else if (cur && line.startsWith("+")) {
      cur.added.push(line.slice(1));
    } else if (cur && line.startsWith("-")) {
      cur.removed.push(line.slice(1));
    }
  }
  return out.filter((c) => c.file !== "");
}

const CHEATS: { rx: RegExp; what: string }[] = [
  { rx: /continue-on-error\s*:\s*true/i, what: "continue-on-error: true (a failure no longer fails the run)" },
  { rx: /\bretry\b|\bretries\b|\brerun|nick-fields\/retry|flaky\s*=|--reruns|pytest\.mark\.flaky|jest\.retryTimes/i, what: "a retry (a test that needs one has a bug)" },
  { rx: /@unittest\.skip|\bskipIf\b|\bskipUnless\b|pytest\.mark\.(skip|xfail)|\b(it|test|describe)\.(skip|only|todo)\b|\bx(it|describe|test)\(|\.skip\(|\.only\(/, what: "a skipped test, or `.only`" },
  { rx: /--no-verify|\bHUSKY\s*=\s*0\b|\bSKIP\s*=/, what: "a bypass of the git hook" },
  { rx: /pull_request_target/, what: "pull_request_target (runs untrusted code with secrets)" },
  { rx: /permissions\s*:\s*write-all|\b(contents|actions|checks|statuses|pull-requests)\s*:\s*write\b/, what: "wider permissions" },
  { rx: /--runInBand\b|(--max-?[Ww]orkers|--workers|--jobs|-j)[= ]1\b|-n[= ]0\b/, what: "fewer workers (check it is not hiding a race)" },
  { rx: /timeout-minutes\s*:\s*\d{3,}/, what: "a very long timeout" },
];

const CHECK_TOOL = /\b(pnpm|npm|yarn|npx|bun|pytest|vitest|jest|tsc|eslint|prettier|ruff|mypy|cargo|go|make|gradle|mvn|bundle|rake|unittest|run-tests?)\b/;

/** A comment changes nothing, so a comment that mentions a rerun is not a retry. */
function code(line: string): string | null {
  if (/^\s*(#|\/\/|\*|\/\*)/.test(line)) return null;
  return line.replace(/\s+#.*$/, "");
}

/** `|| true` after a test, lint or build command hides its failure. After `grep` or `git merge-base` it is ordinary shell. */
export function swallowedFailures(lines: string[]): string[] {
  const found: string[] = [];
  let stmt = "";
  for (const l of lines) {
    const s = l.trim();
    stmt = s.startsWith("||") || stmt.endsWith("\\") ? `${stmt} ${s}` : s;
    if (/\|\|\s*(true\b|:)/.test(s) && CHECK_TOOL.test(stmt)) found.push(stmt.slice(0, 100));
  }
  return found;
}

const NUM_TIMEOUT = /timeout[-_a-z]*\s*[:=]\s*(\d+)/i;
const TEST_FILE = /(^|\/)(tests?|__tests__|spec)\/|\.(test|spec)\.[a-z]+$|(^|\/)test_[^/]*$|_test\.[a-z]+$/;
const ASSERTION = /\b(assert\w*|expect|toBe\w*|toEqual|toMatch\w*|should|require_eq|EXPECT_\w+|ASSERT_\w+)\b/;

/** Everything a change did to go faster that a person must look at. Order: file, then rule. */
export function scanDiff(changes: FileChange[]): Finding[] {
  const out: Finding[] = [];
  for (const c of changes) {
    if (SKIP_FILE.test(c.file)) continue;
    const added = c.added.map(code).filter((l): l is string => l !== null);
    const seen = new Set<string>();
    for (const { rx, what } of CHEATS) {
      const hit = added.find((l) => rx.test(l));
      if (hit && !seen.has(what)) {
        seen.add(what);
        out.push({ kind: "cheat", file: c.file, what, line: hit.trim().slice(0, 100) });
      }
    }
    const swallowed = swallowedFailures(added)[0];
    if (swallowed) out.push({ kind: "cheat", file: c.file, what: "`|| true` after a check", line: swallowed });
    // A timeout that grew: compare the numbers that left with the numbers that arrived.
    const was = c.removed.map((l) => NUM_TIMEOUT.exec(l)?.[1]).filter((v): v is string => v !== undefined).map(Number);
    const now = added.map((l) => NUM_TIMEOUT.exec(l)?.[1]).filter((v): v is string => v !== undefined).map(Number);
    if (was.length && now.length && Math.max(...now) > Math.max(...was)) {
      out.push({ kind: "cheat", file: c.file, what: "a wider timeout", line: `timeout ${Math.max(...was)} -> ${Math.max(...now)}` });
    }
    if (TEST_FILE.test(c.file)) {
      const gone = c.removed.filter((l) => ASSERTION.test(l));
      if (gone.length) {
        out.push({ kind: "review", file: c.file, what: `${gone.length} assertion line(s) changed or removed: a person decides which side was meant`, line: gone[0]!.trim().slice(0, 100) });
      }
    }
  }
  return out;
}

// ── JUnit ─────────────────────────────────────────────────────────────────

export type TestState = "pass" | "fail" | "skip";

function unescapeXml(s: string): string {
  return s
    .replace(/&#x([0-9a-f]+);/gi, (_, h: string) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d: string) => String.fromCodePoint(Number(d)))
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

function attrs(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of text.matchAll(/([A-Za-z_:][\w:.-]*)\s*=\s*"([^"]*)"/g)) out[m[1]!] = unescapeXml(m[2]!);
  return out;
}

/**
 * Every test case in one JUnit file by `classname::name`, added to `into`. A name already there (a
 * parametrised test, or the same test in another shard's file) gets `#2`, `#3`, so none is lost. The
 * report files are read in sorted order on both sides, so the same test gets the same key.
 */
export function parseJUnit(xml: string, into: Map<string, TestState> = new Map()): Map<string, TestState> {
  for (const m of xml.matchAll(/<testcase\b([^>]*?)(?:\/>|>([\s\S]*?)<\/testcase>)/g)) {
    const a = attrs(m[1]!);
    if (a.name === undefined) continue;
    const base = `${a.classname ?? ""}::${a.name}`;
    let key = base;
    for (let n = 2; into.has(key); n++) key = `${base}#${n}`;
    const body = m[2] ?? "";
    into.set(key, /<(failure|error)\b/.test(body) ? "fail" : /<skipped\b/.test(body) ? "skip" : "pass");
  }
  return into;
}

export interface TestComparison {
  before: number;
  after: number;
  stopped: string[];
  newlySkipped: string[];
  newlyFailing: string[];
  added: number;
  ok: boolean;
}

/** A test may not stop running, be newly skipped, or newly fail. New tests are fine. */
export function compareTests(before: Map<string, TestState>, after: Map<string, TestState>): TestComparison {
  const stopped: string[] = [];
  const newlySkipped: string[] = [];
  const newlyFailing: string[] = [];
  for (const [name, was] of before) {
    const now = after.get(name);
    if (now === undefined) stopped.push(name);
    else if (was !== "skip" && now === "skip") newlySkipped.push(name);
    else if (was !== "fail" && now === "fail") newlyFailing.push(name);
  }
  const added = [...after.keys()].filter((k) => !before.has(k)).length;
  return {
    before: before.size,
    after: after.size,
    stopped: stopped.sort(),
    newlySkipped: newlySkipped.sort(),
    newlyFailing: newlyFailing.sort(),
    added,
    ok: stopped.length === 0 && newlySkipped.length === 0 && newlyFailing.length === 0,
  };
}

export function renderTests(c: TestComparison): string {
  const lines = [`tests that ran: before ${c.before}, after ${c.after}${c.added ? ` (${c.added} new)` : ""}`];
  for (const [label, names] of [["stopped running", c.stopped], ["newly skipped", c.newlySkipped], ["newly failing", c.newlyFailing]] as const) {
    if (names.length) lines.push(`${label}:`, ...names.slice(0, 25).map((n) => `  ${n}`), ...(names.length > 25 ? [`  ...and ${names.length - 25} more`] : []));
  }
  lines.push(c.ok ? "verdict: ok: every test that ran before still runs and passes the same way" : "verdict: FAIL: tests lost, skipped or newly failing");
  return lines.join("\n");
}

export function renderFindings(findings: Finding[]): string {
  if (findings.length === 0) return "diff-guard: nothing added that hides a failure, and no assertion removed.";
  const lines: string[] = [];
  for (const f of findings) lines.push(`${f.kind === "cheat" ? "CHEAT " : "REVIEW"} ${f.file}: ${f.what}\n       ${f.line}`);
  const cheats = findings.filter((f) => f.kind === "cheat").length;
  lines.push("", cheats ? `${cheats} change(s) that could hide a failure: each needs a reason a person accepts, or must go.` : "Nothing that hides a failure. Items marked REVIEW are for a person to read.");
  return lines.join("\n");
}
