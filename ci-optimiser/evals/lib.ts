/**
 * Shared helpers for the ci-optimiser evals. Each eval is a made-up repository with one planted
 * cause, a prompt for an agent, and a `check.ts` that says whether the agent fixed the cause
 * without hiding a failure. Nothing here calls a model or the network.
 */
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { parseDiff, scanDiff } from "../skills/ci-optimiser/scripts/guard-lib.ts";

export const SAMPLE_TAG = "sample";
export const EVALS_DIR = dirname(fileURLToPath(import.meta.url));

/** Copy an eval's `repo/` to a fresh folder, commit it and tag the commit `sample`. */
export function prepare(evalName: string): string {
  const dir = mkdtempSync(join(tmpdir(), `ci-eval-${evalName}-`));
  cpSync(join(EVALS_DIR, evalName, "repo"), dir, { recursive: true });
  const g = (...a: string[]): void => void execFileSync("git", ["-C", dir, "-c", "user.email=eval@example.test", "-c", "user.name=eval", ...a], { stdio: "ignore" });
  g("init", "-q");
  g("add", ".");
  g("commit", "-q", "-m", "sample");
  g("tag", SAMPLE_TAG);
  return dir;
}

/** Lay an overlay folder (a correct fix, or a tempting wrong one) over a prepared sample. */
export function overlay(evalName: string, kind: "solution" | "cheat", dir: string): void {
  cpSync(join(EVALS_DIR, evalName, kind), dir, { recursive: true });
}

export function git(dir: string, ...args: string[]): string {
  return execFileSync("git", ["-C", dir, ...args], { encoding: "utf-8", maxBuffer: 64 * 1024 * 1024 });
}

/** The sample as handed over: the tag `run.ts` sets, so an agent that commits cannot move the baseline. */
export function baseRef(dir: string): string {
  try {
    git(dir, "rev-parse", "-q", "--verify", `refs/tags/${SAMPLE_TAG}`);
    return SAMPLE_TAG;
  } catch {
    return "HEAD";
  }
}

/** Hard cheats added anywhere in the change since the sample, as one line each. */
export function cheatsSince(dir: string): string[] {
  const changes = parseDiff(git(dir, "diff", baseRef(dir), "--unified=0", "--no-color"));
  for (const f of git(dir, "ls-files", "--others", "--exclude-standard").split("\n").filter(Boolean)) {
    try {
      changes.push({ file: f, added: readFileSync(join(dir, f), "utf-8").split("\n"), removed: [] });
    } catch {
      // not text
    }
  }
  return scanDiff(changes).filter((f) => f.kind === "cheat").map((f) => `${f.file}: ${f.what}`);
}

/** Every workflow file as text, by repo-relative path. */
export function workflows(dir: string): { file: string; text: string }[] {
  const base = join(dir, ".github/workflows");
  if (!existsSync(base)) return [];
  return readdirSync(base)
    .filter((n) => /\.ya?ml$/.test(n))
    .sort()
    .map((n) => ({ file: `.github/workflows/${n}`, text: readFileSync(join(base, n), "utf-8") }));
}

/** The lines under the top-level `on:` key (and the key itself). */
export function onBlock(text: string): string[] {
  const lines = text.split("\n");
  const start = lines.findIndex((l) => /^["']?on["']?\s*:/.test(l));
  if (start < 0) return [];
  const out = [lines[start]!];
  for (let i = start + 1; i < lines.length; i++) {
    const l = lines[i]!;
    if (l.trim() === "" || /^\s/.test(l)) out.push(l);
    else break;
  }
  return out;
}

/**
 * The branches a `push` trigger is limited to: a list, or null when push is absent, or "all" when it has no
 * `branches:` filter.
 */
export function pushBranches(text: string): string[] | "all" | null {
  const on = onBlock(text);
  const head = (on[0] ?? "").replace(/^[^:]*:/, "");
  if (/\bpush\b/.test(head)) return "all";
  for (let i = 1; i < on.length; i++) {
    if (/^\s*-\s*push\s*$/.test(on[i]!)) return "all";
    if (!/^\s*push\s*:/.test(on[i]!)) continue;
    const indent = on[i]!.length - on[i]!.trimStart().length;
    const body: string[] = [on[i]!.replace(/^\s*push\s*:/, "")];
    for (let j = i + 1; j < on.length && (on[j]!.trim() === "" || on[j]!.length - on[j]!.trimStart().length > indent); j++) body.push(on[j]!);
    const joined = body.join("\n");
    const m = /branches\s*:\s*(\[[^\]]*\]|(?:\n\s*-\s*\S+)+)/.exec(joined);
    if (!m) return "all";
    return [...m[1]!.matchAll(/[\w./*-]+/g)].map((x) => x[0]).filter((x) => x !== "branches");
  }
  return null;
}

export function hasTrigger(text: string, name: string): boolean {
  return onBlock(text).some((l) => new RegExp(`(^|[\\s\\[,-])${name}\\b`).test(l));
}

export class Result {
  failures: string[] = [];
  notes: string[] = [];
  expect(ok: boolean, passMsg: string, failMsg: string): void {
    if (ok) this.notes.push(`ok: ${passMsg}`);
    else this.failures.push(failMsg);
  }
  report(): number {
    for (const n of this.notes) console.log(n);
    for (const f of this.failures) console.log(`FAIL: ${f}`);
    console.log(this.failures.length === 0 ? "PASS" : `FAIL (${this.failures.length})`);
    return this.failures.length === 0 ? 0 : 1;
  }
}
