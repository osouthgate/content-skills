#!/usr/bin/env python3
"""Fixture: print the process's own argv (excluding the script path) and exit 0.

Used by adapter.py's tests to prove that a value reached this child process
as one argv element — never as text a shell parsed or expanded.
"""

import sys

print(repr(sys.argv[1:]))
