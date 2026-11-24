/**
 * Static hints from GitHub Actions workflow files: the ci-optimiser skill's
 * hygiene checklist (references/techniques.md, section 14) as code.
 *
 * It reads YAML as text, line by line, with no YAML library, so the skill stays
 * free of installs. It is a list of places to look, not a verdict: every hint
 * says what to check by hand before changing anything. It never suggests
 * removing a job, a test or a security scan.
 */

export interface Hint {
  file: string;
  /** The job the hint is about, or null for the whole workflow. */
  job: string | null;
  code: string;
  text: string;
}

interface Job {
  name: string;
  body: string[];
}

function indentOf(line: string): number {
  return line.length - line.trimStart().length;
}

/** Top-level keys and the jobs under `jobs:`, by indentation. Comments and blank lines are ignored. */
function outline(text: string): { top: Map<string, string[]>; jobs: Job[] } {
  const lines = text.split("\n").filter((l) => l.trim() !== "" && !l.trimStart().startsWith("#"));
  const top = new Map<string, string[]>();
  let current: string | null = null;
  for (const line of lines) {
    if (indentOf(line) === 0) {
      const m = /^["']?([A-Za-z0-9_-]+)["']?\s*:/.exec(line);
      current = m ? m[1]! : null;
      if (current) top.set(current, [line]);
    } else if (current) top.get(current)!.push(line);
  }
  const jobs: Job[] = [];
  const jobLines = (top.get("jobs") ?? []).slice(1);
  const jobIndent = jobLines.length ? indentOf(jobLines[0]!) : 0;
  for (const line of jobLines) {
    const m = /^\s*["']?([A-Za-z0-9_-]+)["']?\s*:\s*$/.exec(line);
    if (indentOf(line) === jobIndent && m) jobs.push({ name: m[1]!, body: [] });
    else if (jobs.length) jobs.at(-1)!.body.push(line);
  }
  return { top, jobs };
}

/** `on` holds pull_request (as a key, a list item or a flow list). */
function onPullRequest(on: string[]): boolean {
  return on.some((l) => /\bpull_request\b(?!_target)/.test(l));
}

/**
 * `on` holds a `push` trigger with no `branches:` (or `tags:`) filter, so it also
 * fires for every commit on a PR branch. Handles `on: push`, `on: [push, ...]`,
 * a list item and the block form.
 */
function pushWithoutBranchFilter(on: string[]): boolean {
  const inline = (on[0] ?? "").replace(/^[^:]*:/, "");
  if (/\bpush\b/.test(inline)) return true;
  for (let i = 1; i < on.length; i++) {
    const line = on[i]!;
    if (/^\s*-\s*push\s*$/.test(line)) return true;
    if (!/^\s*push\s*:/.test(line)) continue;
    const indent = indentOf(line);
    let filtered = /\b(branches|tags)\b/.test(line.replace(/^\s*push\s*:/, ""));
    for (let j = i + 1; j < on.length && indentOf(on[j]!) > indent; j++) {
      if (/^\s*(branches|tags)\s*:/.test(on[j]!)) filtered = true;
    }
    return !filtered;
  }
  return false;
}

export function scanWorkflow(file: string, text: string): Hint[] {
  const hints: Hint[] = [];
  const { top, jobs } = outline(text);
  const on = top.get("on") ?? [];
  const add = (job: string | null, code: string, t: string): void => {
    hints.push({ file, job, code, text: t });
  };

  if (onPullRequest(on) && pushWithoutBranchFilter(on)) {
    add(
      null,
      "double-trigger",
      "Runs on both `push` (no `branches:` filter) and `pull_request`: a commit on a PR branch can run twice. Check the ledger for the same commit with both events on a non-default branch. Before filtering push to the default branch, confirm the required check is the pull_request one and that the push run has no side effect the PR run lacks (preview deploy, tagged image, cache warm).",
    );
  }

  if (onPullRequest(on) && !top.has("concurrency") && !jobs.some((j) => j.body.some((l) => /^\s*concurrency\s*:/.test(l)))) {
    add(
      null,
      "no-concurrency",
      "Runs on pull_request with no `concurrency` group: a new push does not cancel the older run of the same PR. Check: cancel only PR runs (for example `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`), so every push to the default branch still finishes.",
    );
  }
  for (const job of jobs) {
    const body = job.body.join("\n");
    if (!/^\s*timeout-minutes\s*:/m.test(body)) {
      add(job.name, "no-timeout", "No `timeout-minutes`: a hung step holds a runner for the 6-hour default. Check the job's p90 in the ledger and set a limit well above it.");
    }
    if (/fetch-depth\s*:\s*0\b/.test(body)) {
      add(job.name, "full-history", "`fetch-depth: 0` clones all history. Check whether a step reads history (git log, describe, diff against a base); if not, the default shallow clone is faster. If it does, consider `filter: blob:none`.");
    }
    const setups = [...body.matchAll(/uses\s*:\s*actions\/setup-(node|python|go|java)@/g)].map((m) => m[1]!);
    const installs = /\b(npm (ci|install)|yarn( install)?\b|pnpm install|pip install|poetry install|uv sync|go mod download|bundle install|mvn |gradle)/.test(body);
    if (setups.length && installs && !/^\s*cache\s*:/m.test(body) && !/actions\/cache@/.test(body)) {
      for (const lang of setups) {
        add(job.name, "no-dependency-cache", `actions/setup-${lang} with no \`cache:\` and no actions/cache. The job installs packages. If the install step is slow in the ledger, a cache keyed on the lock file may help; if it takes a few seconds, leave it.`);
      }
    }
    if (/playwright install/.test(body) && !/ms-playwright/.test(body)) {
      add(job.name, "browser-download", "Playwright downloads its browsers on every run. Check that step's time in the ledger; a cache of ~/.cache/ms-playwright keyed on the Playwright version may help.");
    }
    if (/^\s*continue-on-error\s*:\s*true\b/m.test(body)) {
      add(job.name, "masked-failure", "`continue-on-error: true` lets a step or job fail without failing the run. Check whether anyone reads it. Report it to the owner; do not remove or keep it as a speed-up, because it changes what the check proves.");
    }
    if (/^\s*max-parallel\s*:\s*1\s*$/m.test(body)) {
      add(job.name, "serial-matrix", "`max-parallel: 1` runs the matrix one leg at a time. Check why (a shared resource, an ordering need). If the legs are independent, parallel legs cut wall time at the same total cost.");
    }
    if (/(?:^|[\s;&|])sleep\s+\d+/m.test(body)) {
      add(job.name, "fixed-sleep", "A fixed `sleep` waits its full time on every run. Check what it waits for; a health check or a poll on the event usually ends sooner and fails clearer. Keep any wait a test truly needs.");
    }
    if (/^\s*key\s*:.*\$\{\{[^}]*(github\.(sha|run_id|run_number|run_attempt)|now)\b/m.test(body) && !/^\s*restore-keys\s*:/m.test(body)) {
      add(job.name, "unstable-cache-key", "A cache key that holds the commit or run id is new on every run, and there is no `restore-keys` fallback, so it never hits. Check the cache's hit rate in a job log; a key on the lock file's hash is stable until the inputs change.");
    }
    const runSteps = (body.match(/^\s*(?:-\s+)?run\s*:/gm) ?? []).length;
    if (runSteps >= 10 && !/^\s*(strategy|needs)\s*:/m.test(body)) {
      add(job.name, "long-serial-job", `${runSteps} run steps in one job, one after another. If the ledger shows this job sets the wall time, check whether independent groups can run as parallel jobs (each still required, none dropped).`);
    }
  }
  return hints;
}

export function renderHints(hints: Hint[]): string {
  if (hints.length === 0) return "## Workflow hints\n\nNo hints: the checklist found nothing to look at.\n";
  const rows = hints.map((h) => `| \`${h.file}\` | ${h.job ?? "(workflow)"} | ${h.code} | ${h.text.replace(/\|/g, "/")} |`);
  return ["## Workflow hints", "", "Places to look, not verdicts. Check each by hand and by the ledger before any change.", "", "| file | job | hint | what to check |", "| --- | --- | --- | --- |", ...rows, ""].join("\n");
}
