// A made-up service that becomes ready shortly after it starts.
export function startService(readyAfterMs = 50) {
  let ready = false;
  const waiting = [];
  const timer = setTimeout(() => {
    ready = true;
    for (const resolve of waiting.splice(0)) resolve();
  }, readyAfterMs);
  return {
    get ready() {
      return ready;
    },
    /** Resolves as soon as the service is ready. */
    whenReady() {
      return ready ? Promise.resolve() : new Promise((resolve) => waiting.push(resolve));
    },
    stop() {
      clearTimeout(timer);
    },
  };
}
