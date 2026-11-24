import { test } from "node:test";
import assert from "node:assert/strict";

import { startService } from "../src/service.js";

test("the service is ready once it has had time to start", async () => {
  const service = startService();
  await service.whenReady();
  assert.equal(service.ready, true);
  service.stop();
});

test("the service is not ready the moment it starts", () => {
  const service = startService();
  assert.equal(service.ready, false);
  service.stop();
});

test("whenReady resolves once the service is ready", async () => {
  const service = startService(10);
  await service.whenReady();
  assert.equal(service.ready, true);
  service.stop();
});
