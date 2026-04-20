# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helpers for validating debugger plugin output."""

import os
import re


_FRAME_ANNOTATION_RE = re.compile(
  r"\[(?P<function>[^\]@]+) @ (?P<script>.+?):(?P<line>\d+):(?P<column>\d+)\]"
)


def check_frame_annotations(output, script_basename, expected):
  """Check that expected frame annotations appear in the output.

  Args:
    output: combined stdout/stderr from the debugger session.
    script_basename: basename of the JS test script.
    expected: sequence of (function_name, line, column) tuples.

  Returns:
    (missing, found) where missing is a list of unmatched expectations and
    found is the sorted set of all parsed annotations.
  """
  found = set()
  for match in _FRAME_ANNOTATION_RE.finditer(output):
    found.add((
      match.group("function").strip(),
      os.path.basename(match.group("script")),
      int(match.group("line")),
      int(match.group("column")),
    ))

  full_expected = [
    (func, script_basename, line, col) for func, line, col in expected
  ]
  missing = [ann for ann in full_expected if ann not in found]
  return missing, sorted(found)
