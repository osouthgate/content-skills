// Run: node --test tests/*.test.ts   (Node 22.18+; no installs)
import { test } from "node:test";
import assert from "node:assert/strict";

import { scanWorkflow } from "../scripts/workflow-scan.ts";

const codes = (file: string, text: string): string[] => scanWorkflow(file, text).map((h) => h.code).sort();

const job = (extra = ""): string => `jobs:
  a:
    timeout-minutes: 5
    steps:
      - run: echo ok
${extra}`;

test("double-trigger: push with no branch filter plus pull_request", () => {
  assert.deepEqual(codes("a.yml", `on: [push, pull_request]\nconcurrency:\n  group: x\n${job()}`), ["double-trigger"]);
  assert.deepEqual(codes("a.yml", `on:\n  push:\n  pull_request:\nconcurrency:\n  group: x\n${job()}`), ["double-trigger"]);
  assert.deepEqual(codes("a.yml", `on:\n  - push\n  - pull_request\nconcurrency:\n  group: x\n${job()}`), ["double-trigger"]);
});

test("double-trigger stays quiet when push is filtered or there is no pull_request", () => {
  const branches = `on:\n  push:\n    branches: [main]\n  pull_request:\nconcurrency:\n  group: x\n${job()}`;
  assert.deepEqual(codes("a.yml", branches), []);
  const tags = `on:\n  push:\n    tags: ["v*"]\n  pull_request:\nconcurrency:\n  group: x\n${job()}`;
  assert.deepEqual(codes("a.yml", tags), []);
  assert.deepEqual(codes("a.yml", `on: push\n${job()}`), []);
  assert.deepEqual(codes("a.yml", `on:\n  pull_request:\nconcurrency:\n  group: x\n${job()}`), []);
});

test("masked-failure, serial-matrix and fixed-sleep", () => {
  const wf = `on: push
jobs:
  a:
    timeout-minutes: 5
    continue-on-error: true
    strategy:
      max-parallel: 1
      matrix:
        n: [1, 2]
    steps:
      - run: docker compose up -d && sleep 30
`;
  assert.deepEqual(codes("a.yml", wf), ["fixed-sleep", "masked-failure", "serial-matrix"]);
  const expr = `on: push\njobs:\n  a:\n    timeout-minutes: 5\n    continue-on-error: \${{ matrix.experimental }}\n    steps:\n      - run: echo sleeper\n`;
  assert.deepEqual(codes("a.yml", expr), [], "an expression is not a literal true, and a word is not a sleep");
});

test("unstable-cache-key needs a commit or run id and no restore-keys", () => {
  const bad = `on: push\njobs:\n  a:\n    timeout-minutes: 5\n    steps:\n      - uses: actions/cache@v4\n        with:\n          path: ~/.npm\n          key: npm-\${{ github.sha }}\n`;
  assert.deepEqual(codes("a.yml", bad), ["unstable-cache-key"]);
  const withFallback = bad + "          restore-keys: npm-\n";
  assert.deepEqual(codes("a.yml", withFallback), []);
  const stable = bad.replace("github.sha", "hashFiles('package-lock.json')");
  assert.deepEqual(codes("a.yml", stable), []);
});
