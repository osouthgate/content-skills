#!/usr/bin/env python3
"""Fixture: write a fixed line to the file named by argv[1], then exit 0.

A later step in a checks/verify sequence that a test expects to be
skipped points here with a marker path; the test then asserts the file
was never created.
"""

import sys

with open(sys.argv[1], "w", encoding="utf-8") as fh:
    fh.write("ran\n")
