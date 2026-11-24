/**
 * diff-guard: check a CI change against the skill's "never trade proof for speed" rule.
 * Runs with plain `node` (22.18+). SKILL is the folder that holds this skill's SKILL.md.
 *
 *   node SKILL/scripts/diff-guard.ts diff [--base <ref>] [--root <repo>]
 *       Reads the ADDED lines of the change against <ref> (default: the merge-base with the
 *       default branch, else HEAD) and lists what hides a failure. Exit 4 if any "cheat".
 *
 *   node SKILL/scripts/diff-guard.ts tests --before <dir> --after <dir>
 *       Compares JUnit XML reports by test name. Exit 4 if any test stopped running, was
 *       newly skipped or newly fails. Where CI saves no JUnit report this cannot run: say
 *       the check is unverified, and compare the test counts the runner prints.
 *
 * It reads files and git output only. It starts no run and writes nothing.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

import { type FileChange, type TestState, compareTests, parseDiff, parseJUnit, renderFindings, renderTests, scanDiff } from "./guard-lib.ts";

const args = process.argv.slice(2);
const command = args[0];
const flag = (name: string): string | undefined => {
  const i = args.indexOf(name);
  if (i < 0) return undefined;
  const v = args[i + 1];
  if (v === undefined || v.startsWith("--")) throw new Error(`${name} needs a value`);
  return v;
};

function git(root: string, ...a: string[]): string {
  return execFileSync("git", ["-C", root, ...a], { encoding: "utf-8", maxBuffer: 64 * 1024 * 1024 });
}

/** The ref to compare against: the merge-base with origin's default branch when there is one, else HEAD. */
function defaultBase(root: string): string {
  try {
    const head = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").trim();
    return git(root, "merge-base", "HEAD", head).trim();
  } catch {
    return "HEAD";
  }
}

function diffCommand(): number {
  const root = resolve(flag("--root") ?? process.cwd());
  const base = flag("--base") ?? defaultBase(root);
  const changes: FileChange[] = parseDiff(git(root, "diff", base, "--unified=0", "--no-color"));
  // A new file the agent has not added to git yet is part of the change too.
  for (const f of git(root, "ls-files", "--others", "--exclude-standard").split("\n").filter(Boolean)) {
    try {
      changes.push({ file: f, added: readFileSync(join(root, f), "utf-8").split("\n"), removed: [] });
    } catch {
      // unreadable or binary: nothing to scan
    }
  }
  const findings = scanDiff(changes);
  console.log(renderFindings(findings));
  return findings.some((f) => f.kind === "cheat") ? 4 : 0;
}

/** Every `*.xml` under a folder, two levels deep, merged into one map of tests. */
function readReports(dir: string): Map<string, TestState> {
  const abs = resolve(dir);
  if (!existsSync(abs) || !statSync(abs).isDirectory()) throw new Error(`${dir}: not a folder of JUnit reports`);
  const out = new Map<string, TestState>();
  const walk = (d: string, depth: number): number => {
    let files = 0;
    for (const name of readdirSync(d).sort()) {
      const p = join(d, name);
      if (statSync(p).isDirectory()) {
        if (depth < 2) files += walk(p, depth + 1);
      } else if (name.endsWith(".xml")) {
        parseJUnit(readFileSync(p, "utf-8"), out);
        files += 1;
      }
    }
    return files;
  };
  if (walk(abs, 0) === 0) throw new Error(`${dir}: no .xml reports found`);
  return out;
}

function testsCommand(): number {
  const before = flag("--before");
  const after = flag("--after");
  if (!before || !after) throw new Error("tests needs --before <dir> and --after <dir>: each a new, empty folder of JUnit XML downloaded from the CI run");
  const result = compareTests(readReports(before), readReports(after));
  console.log(renderTests(result));
  return result.ok ? 0 : 4;
}

try {
  if (command === "diff") process.exit(diffCommand());
  if (command === "tests") process.exit(testsCommand());
  console.error("usage: diff-guard.ts <diff [--base ref] [--root dir] | tests --before dir --after dir>");
  process.exit(2);
} catch (err) {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
}
