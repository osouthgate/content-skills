/**
 * The ci-optimiser skill's ledger CLI: keep a history of every CI run, and read it.
 * Runs with plain `node` (22.18+, which strips TypeScript types itself) from the
 * project root. SKILL is the folder that holds this skill's SKILL.md.
 *
 *   node SKILL/scripts/ledger.ts pull                      # completed runs of the last 2 days
 *   node SKILL/scripts/ledger.ts pull --since 14d          # or --since 2026-11-01
 *   node SKILL/scripts/ledger.ts pull --workflow ci.yml    # one workflow only
 *   node SKILL/scripts/ledger.ts import <dir>              # saved API responses: runs.json + jobs-<runId>.json
 *   node SKILL/scripts/ledger.ts report                    # last 7 days vs the 7 before
 *   node SKILL/scripts/ledger.ts report --days 30 --branch main --top 20
 *   node SKILL/scripts/ledger.ts compare --job test --label ubuntu-latest \
 *     --before 2026-11-01..2026-11-10T14:00:00Z --after 2026-11-10T14:00:00Z..2026-11-14
 *
 * `compare` gives a before / after verdict for one job (or, with --metric wall --workflow NAME,
 * one workflow's wall time): the median shift with an exact 95% interval, and the failure rates.
 * Choose both windows before looking. It needs 5 passed comparable runs a side, refuses a window
 * that has not settled (fast runs finish first), and exits 3 for too few runs and 4 when more runs
 * failed after than chance explains. Flags: --event (default pull_request), --branch, --label,
 * --workflow, --settle <hours, default 2>, --assume-settled (for a ledger made with `import`),
 * --min-runs (5 or more), --out <file>.
 *
 * Flags: --root <project root, default cwd>, --repo owner/name, --dir <ledger dir,
 * default docs/ledger/ci>, --report-dir <default test-results/ci-ledger>, --out <file>.
 *
 * `pull` needs a token that can read Actions: GITHUB_TOKEN or GH_TOKEN, or a
 * logged-in `gh` (`gh auth token`). It reads only; it never writes to GitHub.
 * The repository comes from `--repo`, else GITHUB_REPOSITORY, else the
 * `origin` remote's URL. It asks for one day at a time, because the runs API
 * returns at most 1,000 runs for one filtered query; a day at that cap is
 * reported as incomplete, not hidden.
 *
 * A pull merges by run key, so it is safe to repeat. Whether the day files
 * (<ledger dir>/<YYYY-MM-DD>.jsonl) are committed is the repository owner's
 * choice: they hold branch names, commit titles and runner names.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

import {
  type CompareOptions,
  type PullState,
  CompareError,
  compareSamples,
  renderComparison,
  selectSamples,
  settledProblem,
} from "./compare-lib.ts";
import {
  type LedgerRun,
  type RawJob,
  type RawRun,
  byDay,
  formatDay,
  mergeDay,
  normaliseRun,
  parseDay,
  parseJobs,
  parseRuns,
  renderReport,
  runKey,
} from "./ledger-lib.ts";

const args = process.argv.slice(2);
const command = args[0];
const VALUE_FLAGS = new Set([
  "--root", "--dir", "--report-dir", "--repo", "--since", "--workflow", "--days", "--top", "--branch", "--out",
  "--job", "--label", "--event", "--before", "--after", "--metric", "--settle", "--min-runs",
]);
const flag = (name: string): string | undefined => {
  const i = args.indexOf(name);
  if (i < 0) return undefined;
  const v = args[i + 1];
  if (v === undefined || v.startsWith("--")) throw new Error(`${name} needs a value`);
  return v;
};
/** Arguments that are not flags or flag values, after the command. */
function positionals(): string[] {
  const out: string[] = [];
  for (let i = 1; i < args.length; i++) {
    if (VALUE_FLAGS.has(args[i]!)) i++;
    else if (!args[i]!.startsWith("--")) out.push(args[i]!);
  }
  return out;
}
function positiveInt(name: string, fallback: number): number {
  const v = flag(name);
  if (v === undefined) return fallback;
  if (!/^[1-9]\d{0,4}$/.test(v)) throw new Error(`${name}: expected a whole number from 1, got "${v}"`);
  return Number(v);
}
const ROOT = resolve(flag("--root") ?? process.cwd());
const LEDGER = resolve(ROOT, flag("--dir") ?? "docs/ledger/ci");
const REPORT_DIR = resolve(ROOT, flag("--report-dir") ?? "test-results/ci-ledger");

/** owner/name from --repo, GITHUB_REPOSITORY, or the origin remote (https or ssh, any proxy prefix). */
function repoName(): string {
  const given = flag("--repo") ?? process.env.GITHUB_REPOSITORY;
  if (given) return given;
  try {
    const url = execFileSync("git", ["remote", "get-url", "origin"], { cwd: ROOT, encoding: "utf-8" }).trim();
    const m = /[/:]([^/:]+)\/([^/]+?)(?:\.git)?$/.exec(url);
    if (m) return `${m[1]}/${m[2]}`;
  } catch {
    // fall through
  }
  throw new Error("cannot tell which repository: pass --repo owner/name or set GITHUB_REPOSITORY");
}

function loadLedger(): LedgerRun[] {
  if (!existsSync(LEDGER)) return [];
  const out: LedgerRun[] = [];
  for (const f of readdirSync(LEDGER).filter((n) => /^\d{4}-\d{2}-\d{2}\.jsonl$/.test(n)).sort()) {
    out.push(...parseDay(readFileSync(join(LEDGER, f), "utf-8"), f));
  }
  return out;
}

function writeRuns(runs: LedgerRun[]): { files: number; added: number } {
  mkdirSync(LEDGER, { recursive: true });
  let files = 0;
  let added = 0;
  for (const [day, incoming] of byDay(runs)) {
    // byDay → dayOf already refuses a non-date; checked again here because this line builds a path.
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) throw new Error(`ci-ledger: refusing day file name "${day}"`);
    const path = join(LEDGER, `${day}.jsonl`);
    const existing = existsSync(path) ? parseDay(readFileSync(path, "utf-8"), `${day}.jsonl`) : [];
    const known = new Set(existing.map((r) => r.key));
    added += incoming.filter((r) => !known.has(r.key)).length;
    const next = formatDay(mergeDay(existing, incoming));
    if (!existsSync(path) || readFileSync(path, "utf-8") !== next) {
      writeFileSync(path, next);
      files += 1;
    }
  }
  return { files, added };
}

function sinceDate(value: string | undefined): string {
  const v = value ?? "2d";
  const m = /^(\d+)d$/.exec(v);
  if (m) return new Date(Date.now() - Number(m[1]) * 86_400_000).toISOString().slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
  throw new Error(`--since: expected <n>d or YYYY-MM-DD, got "${v}"`);
}

function token(): string {
  const env = process.env.GITHUB_TOKEN ?? process.env.GH_TOKEN;
  if (env) return env;
  try {
    return execFileSync("gh", ["auth", "token"], { encoding: "utf-8" }).trim();
  } catch {
    throw new Error("no GitHub token: set GITHUB_TOKEN or GH_TOKEN, or log in with `gh auth login`");
  }
}

async function getJson(url: string, auth: string): Promise<unknown> {
  for (let attempt = 1; ; attempt++) {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${auth}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" },
    });
    if (res.ok) return (await res.json()) as unknown;
    // Retry only what can pass on retry: a rate limit (429, or 403 with no requests left or a
    // Retry-After) and server errors. A 403 for missing access fails at once.
    const limited = res.status === 429 || (res.status === 403 && (res.headers.get("x-ratelimit-remaining") === "0" || res.headers.has("retry-after")));
    if ((limited || res.status >= 500) && attempt < 4) {
      const after = Number(res.headers.get("retry-after"));
      const wait = Number.isFinite(after) && after > 0 ? Math.min(after, 60) * 1000 : 2000 * attempt;
      await new Promise((r) => setTimeout(r, wait));
      continue;
    }
    throw new Error(`GitHub ${res.status} for ${url}: ${(await res.text()).slice(0, 200)}`);
  }
}

/** When this machine last pulled, and from which day. It lives in the report folder, which is not committed. */
const PULL_STATE = join(REPORT_DIR, "pull-state.json");

function readPullState(): PullState | null {
  try {
    const v = JSON.parse(readFileSync(PULL_STATE, "utf-8")) as Record<string, unknown>;
    if (typeof v.pulledAt === "string" && typeof v.since === "string") {
      return { pulledAt: v.pulledAt, since: v.since, workflow: typeof v.workflow === "string" ? v.workflow : null };
    }
  } catch {
    // no record: compare will say so
  }
  return null;
}

/** Requests left for this token, and when the limit resets. Null when the endpoint cannot be read. */
async function coreRemaining(auth: string): Promise<{ remaining: number; reset: string } | null> {
  try {
    const body = (await getJson("https://api.github.com/rate_limit", auth)) as { resources?: { core?: { remaining?: number; reset?: number } } };
    const core = body.resources?.core;
    if (typeof core?.remaining !== "number") return null;
    return { remaining: core.remaining, reset: typeof core.reset === "number" ? new Date(core.reset * 1000).toISOString() : "unknown" };
  } catch {
    return null;
  }
}

function daysFrom(since: string, until: Date): string[] {
  const out: string[] = [];
  const end = until.toISOString().slice(0, 10);
  for (let d = new Date(`${since}T00:00:00Z`); d.toISOString().slice(0, 10) <= end; d = new Date(d.getTime() + 86_400_000)) {
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

async function pull(): Promise<void> {
  const repo = repoName();
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) throw new Error(`--repo: expected owner/name, got "${repo}"`);
  const since = sinceDate(flag("--since"));
  const workflow = flag("--workflow");
  const auth = token();
  const known = new Set(loadLedger().map((r) => r.key));
  const base = workflow
    ? `https://api.github.com/repos/${repo}/actions/workflows/${encodeURIComponent(workflow)}/runs`
    : `https://api.github.com/repos/${repo}/actions/runs`;
  const runs: RawRun[] = [];
  const capped: string[] = [];
  for (const day of daysFrom(since, new Date())) {
    let got = 0;
    for (let page = 1; page <= 10; page++) {
      const body = await getJson(`${base}?status=completed&created=${day}&per_page=100&page=${page}`, auth);
      const batch = parseRuns(body);
      runs.push(...batch);
      got += batch.length;
      if (batch.length < 100) break;
    }
    if (got >= 1000) capped.push(day);
  }
  const fresh = runs.filter((r) => !known.has(runKey(r.id, r.run_attempt ?? 1)));
  // One request per new run at least. Stop before reading half and leaving a gap nobody notices.
  const quota = await coreRemaining(auth);
  if (quota && quota.remaining < fresh.length + 50) {
    throw new Error(
      `ci-ledger pull: ${fresh.length} new runs need at least ${fresh.length} GitHub API requests, and ${quota.remaining} are left (they reset ${quota.reset}). Narrow --since, pass --workflow, or wait. Nothing was written.`,
    );
  }
  const out: LedgerRun[] = [];
  for (const r of fresh) {
    const jobs: RawJob[] = [];
    for (let page = 1; page <= 10; page++) {
      const batch = parseJobs(
        await getJson(`https://api.github.com/repos/${repo}/actions/runs/${r.id}/attempts/${r.run_attempt ?? 1}/jobs?per_page=100&page=${page}`, auth),
      );
      jobs.push(...batch);
      if (batch.length < 100) break;
    }
    out.push(normaliseRun(r, jobs));
  }
  const w = writeRuns(out);
  console.log(`ci-ledger pull: ${runs.length} completed runs since ${since}, ${fresh.length} new; ${w.added} lines added in ${w.files} day files (${LEDGER}).`);
  if (capped.length) {
    console.error(`ci-ledger pull: INCOMPLETE. GitHub returned its 1,000-run cap for ${capped.join(", ")}; pull those days per workflow (--workflow).`);
    process.exitCode = 3;
    return;
  }
  // Only a complete pull is recorded: `compare` uses it to know the windows had settled.
  const state: PullState = { pulledAt: new Date().toISOString().replace(/\.\d+Z$/, "Z"), since, workflow: workflow ?? null };
  mkdirSync(REPORT_DIR, { recursive: true });
  writeFileSync(PULL_STATE, JSON.stringify(state) + "\n");
}

/** Import saved responses: `runs.json` (a runs list) and `jobs-<runId>.json` (a jobs list) per run. */
function importDir(dir: string): void {
  const runs = parseRuns(JSON.parse(readFileSync(join(dir, "runs.json"), "utf-8")) as unknown);
  const out: LedgerRun[] = [];
  let missing = 0;
  for (const r of runs) {
    const p = join(dir, `jobs-${r.id}.json`);
    if (!existsSync(p)) {
      missing += 1;
      continue;
    }
    out.push(normaliseRun(r, parseJobs(JSON.parse(readFileSync(p, "utf-8")) as unknown)));
  }
  const w = writeRuns(out);
  console.log(`ci-ledger import: ${out.length} runs (${missing} skipped: no jobs file); ${w.added} lines added in ${w.files} day files.`);
}

function report(): void {
  const days = positiveInt("--days", 7);
  const top = positiveInt("--top", 15);
  const branch = flag("--branch") ?? "main";
  const md = renderReport(loadLedger(), { days, now: new Date(), branch, top, source: `${relative(ROOT, LEDGER) || "."}/` });
  mkdirSync(REPORT_DIR, { recursive: true });
  const outFlag = flag("--out");
  const out = outFlag ? resolve(ROOT, outFlag) : join(REPORT_DIR, "report.md");
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, md + "\n");
  console.log(md);
  console.error(`\nWritten to ${out}`);
}

/** `FROM..TO` in UTC: each end is YYYY-MM-DD or an ISO datetime ending in Z. Returned in the ledger's own format. */
function parseWindow(name: string): { from: string; to: string } {
  const v = flag(name);
  const parts = v === undefined ? [] : v.split("..");
  if (v === undefined || parts.length !== 2 || !parts[0] || !parts[1]) throw new Error(`${name} is required, as FROM..TO in UTC (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)`);
  const at = (s: string): string => {
    const t = /^\d{4}-\d{2}-\d{2}$/.test(s) ? `${s}T00:00:00Z` : s;
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?Z$/.test(t) || Number.isNaN(Date.parse(t))) {
      throw new Error(`${name}: "${s}" is not a UTC date or datetime ending in Z`);
    }
    return new Date(t).toISOString().replace(/\.\d+Z$/, "Z");
  };
  const w = { from: at(parts[0]), to: at(parts[1]) };
  if (w.from >= w.to) throw new Error(`${name}: the window ends before it starts`);
  return w;
}

function compare(): void {
  const metric = flag("--metric") ?? "job";
  if (metric !== "job" && metric !== "wall") throw new Error(`--metric: expected job or wall, got "${metric}"`);
  const before = parseWindow("--before");
  const after = parseWindow("--after");
  if (before.to > after.from) throw new Error("--before and --after overlap: the before window must end where the after window starts or earlier");
  const settleHours = positiveInt("--settle", 2);
  const minRuns = positiveInt("--min-runs", 5);
  const problem = settledProblem({ state: readPullState(), before, after, now: new Date(), settleHours, assumeSettled: args.includes("--assume-settled") });
  if (problem) {
    console.error(`ci-ledger compare: refused: ${problem}`);
    process.exit(2);
  }
  const opts: CompareOptions = {
    job: flag("--job"),
    workflow: flag("--workflow"),
    label: flag("--label"),
    event: flag("--event") ?? "pull_request",
    branch: flag("--branch"),
    metric,
    before,
    after,
  };
  try {
    const samples = selectSamples(loadLedger(), opts);
    const span = (s: { firstAt: string | null; lastAt: string | null }): number => (s.firstAt && s.lastAt ? (Date.parse(s.lastAt) - Date.parse(s.firstAt)) / 86_400_000 : 0);
    const result = compareSamples(samples.before, samples.after, { before: span(samples.before), after: span(samples.after) }, minRuns);
    const text = renderComparison(result, opts);
    console.log(text);
    const outFlag = flag("--out");
    if (outFlag) {
      const out = resolve(ROOT, outFlag);
      mkdirSync(dirname(out), { recursive: true });
      writeFileSync(out, text + "\n");
    }
    if (result.verdict === "not enough runs yet") process.exitCode = 3;
    else if (result.verdict === "not valid: more runs failed after") process.exitCode = 4;
  } catch (err) {
    if (err instanceof CompareError) {
      console.error(`ci-ledger compare: ${err.message}`);
      process.exit(2);
    }
    throw err;
  }
}

async function main(): Promise<void> {
  if (command === "pull") return pull();
  const dir = positionals()[0];
  if (command === "import" && dir) return importDir(resolve(ROOT, dir));
  if (command === "report") return report();
  if (command === "compare") return compare();
  console.error(
    "usage: ledger.ts <pull [--since 14d] [--workflow ci.yml] [--repo o/r] | import <dir> | report [--days 7] [--branch main] [--top 15] [--out f] | compare --job NAME --before FROM..TO --after FROM..TO [--label L] [--event pull_request] [--workflow W] [--metric job|wall] [--settle 2] [--assume-settled] [--min-runs 5] [--out f]>",
  );
  process.exit(2);
}

main().catch((err: unknown) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
