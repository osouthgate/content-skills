/**
 * Prepare one eval, optionally run an agent on it, then run its check.
 *
 *   node evals/run.ts <name>                       # make the sample repo, print what to do
 *   node evals/run.ts <name> --agent '<command>'   # also run your agent there, then check
 *   node evals/run.ts <name> --check <dir>         # only check a repo you already worked in
 *
 * The agent command runs in the sample folder with the prompt in $EVAL_PROMPT_FILE and the same
 * text in $EVAL_PROMPT. Example for Claude Code:
 *
 *   --agent 'claude -p "$EVAL_PROMPT" --permission-mode acceptEdits'
 *
 * A real agent run can make paid calls on your account: this script never starts one unless you
 * pass --agent. The sample folder is left in place so you can read what the agent did; it is under
 * your temp folder, so delete it when you are done.
 */
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { EVALS_DIR as HERE, prepare } from "./lib.ts";

const args = process.argv.slice(2);
const name = args[0];
const flag = (n: string): string | undefined => {
  const i = args.indexOf(n);
  return i < 0 ? undefined : args[i + 1];
};

if (!name || name.startsWith("--") || !existsSync(join(HERE, name, "check.ts"))) {
  console.error("usage: run.ts <cache-seed|double-trigger|slow-sleep> [--agent 'command'] [--check dir]");
  process.exit(2);
}

function check(dir: string): number {
  return spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", join(HERE, name!, "check.ts"), dir], { stdio: "inherit" }).status ?? 1;
}

const only = flag("--check");
if (only) process.exit(check(resolve(only)));

const dir = prepare(name);
const promptFile = join(HERE, name, "prompt.md");
const prompt = readFileSync(promptFile, "utf-8");
console.log(`sample repository: ${dir}`);
const agent = flag("--agent");
if (!agent) {
  console.log(`\nRun your agent in that folder with this prompt (${promptFile}):\n\n${prompt}\nThen check it:\n  node evals/run.ts ${name} --check ${dir}`);
  process.exit(0);
}
const ran = spawnSync("sh", ["-c", agent], { cwd: dir, stdio: "inherit", env: { ...process.env, EVAL_PROMPT: prompt, EVAL_PROMPT_FILE: promptFile } });
if (ran.status !== 0) console.error(`agent command exited with ${ran.status}; checking what it left anyway`);
process.exit(check(dir));
