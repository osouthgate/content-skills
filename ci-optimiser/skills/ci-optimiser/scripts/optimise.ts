/**
 * Gather everything the ci-optimiser skill reads into one brief, so a session
 * starts from one file. Plain `node` (22.18+), from the project root.
 * SKILL is the folder that holds this skill's SKILL.md.
 *
 *   node SKILL/scripts/optimise.ts                 # report over the ledger as it is
 *   node SKILL/scripts/optimise.ts --pull          # pull new runs first (needs a GitHub token)
 *   … --days 14 --branch main --root <project root> --repo owner/name --dir <ledger dir>
 *   … --test-report <file>                         # a per-test-file cost report you made, added as is
 *
 * Writes <root>/test-results/ci-optimiser/brief.md (or --out) with:
 *   1. the CI ledger report: workflows, jobs, slowest steps, trends, and the
 *      commit where a job changed speed (ledger-lib.ts, beside this file);
 *   2. workflow hints from .github/workflows (workflow-scan.ts): places to look,
 *      not verdicts;
 *   3. a per-test-file cost report, when you pass one with --test-report;
 *   4. what each source could not see, so a gap is not read as "fast".
 *
 * It runs no project commands: no package scripts, no tests, no installs.
 */
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { renderHints, scanWorkflow, type Hint } from "./workflow-scan.ts";

const args = process.argv.slice(2);
const flag = (name: string): string | undefined => {
  const i = args.indexOf(name);
  if (i < 0) return undefined;
  const v = args[i + 1];
  if (v === undefined || v.startsWith("--")) throw new Error(`${name} needs a value`);
  return v;
};
const ROOT = resolve(flag("--root") ?? process.cwd());
const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(ROOT, flag("--out") ?? "test-results/ci-optimiser/brief.md");
const REPORT_DIR = join(dirname(OUT), "ledger");

/** Run the ledger CLI beside this file with the same node. */
function ledger(label: string, cmd: string[]): boolean {
  const pass = ["--root", ROOT, "--report-dir", REPORT_DIR];
  for (const f of ["--repo", "--dir"]) {
    const v = flag(f);
    if (v) pass.push(f, v);
  }
  const r = spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", join(HERE, "ledger.ts"), ...cmd, ...pass], {
    cwd: ROOT,
    encoding: "utf-8",
    maxBuffer: 64 * 1024 * 1024,
  });
  if (r.status !== 0) console.error(`ci-optimiser: ${label} failed (exit ${r.status}):\n${(r.stderr || r.stdout).slice(-2000)}`);
  return r.status === 0;
}

function section(path: string, fallback: string): string {
  return existsSync(path) ? readFileSync(path, "utf-8").replace(/^# /m, "## ") : fallback;
}

const days = flag("--days") ?? "7";
if (!/^[1-9]\d{0,4}$/.test(days)) throw new Error(`--days: expected a whole number from 1, got "${days}"`);
const branch = flag("--branch") ?? "main";
const gaps: string[] = [];

if (args.includes("--pull") && !ledger("ledger pull", ["pull", "--since", `${Number(days) * 2}d`])) {
  gaps.push("The ledger pull failed or was incomplete, so the report covers only runs already in the ledger.");
}
if (!ledger("ledger report", ["report", "--days", days, "--branch", branch])) gaps.push("The ledger report failed; see the error above.");

const wfDir = join(ROOT, ".github/workflows");
const hints: Hint[] = [];
if (existsSync(wfDir)) {
  for (const f of readdirSync(wfDir).filter((n) => /\.ya?ml$/.test(n)).sort()) {
    hints.push(...scanWorkflow(`.github/workflows/${f}`, readFileSync(join(wfDir, f), "utf-8")));
  }
} else gaps.push("No .github/workflows folder, so there are no workflow hints.");

const testReport = flag("--test-report");
if (!testReport) {
  gaps.push("No per-test-file cost (pass --test-report <file>). Job and step times only; see references/techniques.md section 0 for how to measure files.");
}
gaps.push("The ledger holds only runs someone has pulled. A day with no file is a day nobody pulled, not a day with no CI.");
gaps.push("Jobs that never started (for example, an Actions billing or spending limit) show as failed with no time. They are not fast.");

const brief = [
  `# CI optimiser brief: ${new Date().toISOString().slice(0, 10)}`,
  "",
  "Read the skill's SKILL.md for what to do with it.",
  "",
  section(join(REPORT_DIR, "report.md"), "## CI report\n\nNo report: the ledger is empty. Run with --pull first."),
  "",
  renderHints(hints),
  testReport ? section(resolve(ROOT, testReport), `## Test file costs\n\n${testReport} was not found.`) : "",
  "",
  "## What this brief could not see",
  "",
  ...gaps.map((g) => `- ${g}`),
  "",
].join("\n");

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, brief);
console.log(`ci-optimiser: brief written to ${OUT} (${brief.length} chars).`);
