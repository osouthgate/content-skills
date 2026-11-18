/**
 * Static hints from GitHub Actions workflow files: the ci-optimiser skill's
 * hygiene checklist (references/techniques.md, section 12) as code.
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

export function scanWorkflow(file: string, text: string): Hint[] {
  const hints: Hint[] = [];
  const { top, jobs } = outline(text);
  const on = top.get("on") ?? [];
  const add = (job: string | null, code: string, t: string): void => {
    hints.push({ file, job, code, text: t });
  };

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
