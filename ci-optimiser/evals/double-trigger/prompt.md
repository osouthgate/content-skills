CI minutes on this repository look wasteful. Use the ci-optimiser skill: read the ledger in
`docs/ledger/ci/`, find the biggest avoidable cost, find its cause in the workflows, and make the
one change that fixes it. Do not change repository settings, and keep the required check named
`test`. Change only what the cause needs, and stop when it is done.
