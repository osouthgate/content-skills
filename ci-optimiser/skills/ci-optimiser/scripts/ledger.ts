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
const VALUE_FLAGS = new Set(["--root", "--dir", "--report-dir", "--repo", "--since", "--workflow", "--days", "--top", "--branch", "--out"]);
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
  }
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

async function main(): Promise<void> {
  if (command === "pull") return pull();
  const dir = positionals()[0];
  if (command === "import" && dir) return importDir(resolve(ROOT, dir));
  if (command === "report") return report();
  console.error("usage: ledger.ts <pull [--since 14d] [--workflow ci.yml] [--repo o/r] | import <dir> | report [--days 7] [--branch main] [--top 15] [--out f]>");
  process.exit(2);
}

main().catch((err: unknown) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
