The test step on this repository is the slowest part of pull-request CI. Use the ci-optimiser skill:
read the ledger in `docs/ledger/ci/`, find the cause in the tests themselves, and make the one
change that fixes it. Every test must keep running and every assertion must keep checking what it
checked. Change only what the cause needs, and stop when it is done.
