# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helpers for validating debugger frame annotations."""

import os
import re


_ANNOTATION_RE = re.compile(
  r"\[(?P<function>[^\]@]+) @ (?P<script>.+?):(?P<line>\d+):(?P<column>\d+)\]"
)


def find_missing_annotations(output, expected_annotations):
  annotations = set()
  for match in _ANNOTATION_RE.finditer(output):
    annotations.add((
      match.group("function").strip(),
      os.path.basename(match.group("script")),
      int(match.group("line")),
      int(match.group("column")),
    ))

  missing = [annotation for annotation in expected_annotations
             if annotation not in annotations]
  return missing, sorted(annotations)