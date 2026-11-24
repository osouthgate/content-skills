// Run: node --test tests/*.test.ts   (Node 22.18+; no installs)
//
// The evals under ci-optimiser/evals/ are made-up repositories with a planted cause, plus a check
// that says whether an agent fixed it without hiding a failure. No agent runs here. These tests prove
// the CHECKS work: each must fail on the sample as handed over, pass a correct fix, and fail a tempting
// wrong one. A check that cannot tell those apart would pass or fail an agent for no reason.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// The skill folder can be copied on its own (SKILL.md says so); the evals live in the plugin folder
// beside it. When they are not there these tests skip instead of crashing on the import.
const LIB = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "evals", "lib.ts");
const present = existsSync(LIB);
const { EVALS_DIR, overlay, prepare } = (present ? await import(LIB) : {}) as typeof import("../../../evals/lib.ts");
const opts = { skip: present ? false : "the evals folder is not next to this skill (a skill copied on its own)" };

function check(name: string, dir: string): { status: number | null; out: string } {
  const r = spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", join(EVALS_DIR, name, "check.ts"), dir], { encoding: "utf-8" });
  return { status: r.status, out: r.stdout + r.stderr };
}

function withSample(name: string, fn: (dir: string) => void): void {
  const dir = prepare(name);
  try {
    fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const EVALS: { name: string; unfixed: RegExp; cheat: RegExp }[] = [
  {
    name: "cache-seed",
    unfixed: /no workflow that runs on a push to main \(or a schedule\) saves a cache/,
    cheat: /lost its lock file hash|does not use the PR job's key/,
  },
  {
    name: "double-trigger",
    unfixed: /still runs on a push to any branch/,
    cheat: /no longer runs on pull_request|preview\.yml was changed/,
  },
  {
    name: "slow-sleep",
    unfixed: /the fixed wait is still there/,
    cheat: /tests lost, skipped or newly failing|adds something that hides a failure/,
  },
];

for (const e of EVALS) {
  test(`eval ${e.name}: every part is present`, opts, () => {
    for (const f of ["prompt.md", "check.ts", "repo", "solution", "cheat"]) assert.ok(existsSync(join(EVALS_DIR, e.name, f)), `${e.name}/${f} is missing`);
    assert.ok(existsSync(join(EVALS_DIR, e.name, "repo/docs/ledger/ci")), "the sample carries a made-up ledger for the agent to read");
  });

  test(`eval ${e.name}: the sample as handed over fails the check (the cause is planted)`, opts, () => {
    withSample(e.name, (dir) => {
      const r = check(e.name, dir);
      assert.equal(r.status, 1, r.out);
      assert.match(r.out, e.unfixed);
    });
  });

  test(`eval ${e.name}: a correct fix passes`, opts, () => {
    withSample(e.name, (dir) => {
      overlay(e.name, "solution", dir);
      const r = check(e.name, dir);
      assert.equal(r.status, 0, r.out);
      assert.match(r.out, /^PASS$/m);
    });
  });

  test(`eval ${e.name}: a tempting wrong fix fails, and says why`, opts, () => {
    withSample(e.name, (dir) => {
      overlay(e.name, "cheat", dir);
      const r = check(e.name, dir);
      assert.equal(r.status, 1, r.out);
      assert.match(r.out, e.cheat);
    });
  });
}

test("evals/run.ts refuses an unknown eval and never starts an agent unasked", opts, () => {
  const run = (...a: string[]) => spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", join(EVALS_DIR, "run.ts"), ...a], { encoding: "utf-8" });
  assert.equal(run("nope").status, 2);
  const r = run("cache-seed");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /sample repository: /);
  assert.match(r.stdout, /Run your agent in that folder/);
  const dir = /sample repository: (.+)/.exec(r.stdout)?.[1];
  assert.ok(dir && existsSync(join(dir, ".git")), "a git repository tagged `sample` was made");
  if (dir) rmSync(dir, { recursive: true, force: true });
});
