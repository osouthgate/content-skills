#!/usr/bin/env python3
"""Fixture: print a marker line to stderr and exit 3 — a deterministic failing check.

Exit code 3 (rather than 1) makes it unambiguous in a test that this
script, and not some other failure, is what stopped a sequence.
"""

import sys

print("fixture fail.py ran", file=sys.stderr)
sys.exit(3)
