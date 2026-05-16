# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Helpers for validating rendered debugger backtrace annotations."""

from collections import Counter
import os
import re

_BACKTRACE_ANNOTATION_LINE_RE = re.compile(
    r"(?P<annotation>\[[^\[\]]*? @ [^\[\]]+?(?::\d+:\d+)?\])"
    r"(?:\s*\([^\)]*\))?\s*$")
_SCRIPT_ANNOTATION_RE = re.compile(
    r"^\[(?P<function>.+?) @ (?P<script>.+?):(?P<line>\d+):(?P<column>\d+)\]$")
_SCRIPT_ONLY_ANNOTATION_RE = re.compile(
    r"^\[(?P<function>.+?) @ (?P<script>.+)\]$")
_FUNCTION_NAME_RE = re.compile(r"^(?P<name>[^\(]+)(?P<call>\(.*\))?$")

# Default expected backtrace for fixtures/throw.js. Brief content (the
# `(this=..., ...)` segment after the function name) is matched separately so
# the assertions stay readable even when debug-helper's per-type brief
# wording shifts.
_DEFAULT_EXPECTED_ANNOTATIONS = (
    ("test_func_3", "<base>/throw.js:15:21"),
    ("<anonymous>", "<base>/throw.js:10:19"),
    ("test_func_2", "<base>/throw.js:9:21"),
    ("test_func_1", "<base>/throw.js:5:21"),
    ("<anonymous>", "<base>/throw.js:1:1"),
)


def _normalize_annotation(annotation):
  """Reduce debugger-specific paths to a (function, location) pair.

  The first element keeps any `(...)` brief suffix attached to the function
  name; the second is `<base>/<script>:<line>:<col>` or `<base>/<script>`.
  """
  annotation = annotation.strip()
  match = _SCRIPT_ANNOTATION_RE.match(annotation)
  if match:
    return (
        match.group("function").strip(),
        f"<base>/{os.path.basename(match.group('script'))}"
        f":{match.group('line')}:{match.group('column')}",
    )
  match = _SCRIPT_ONLY_ANNOTATION_RE.match(annotation)
  if not match:
    return (annotation, None)
  return (
      match.group("function").strip(),
      f"<base>/{os.path.basename(match.group('script'))}",
  )


def _split_function_and_call(function):
  """Split `name(call_suffix)` into (`name`, `call_suffix`); empty if absent."""
  if function is None:
    return (None, "")
  m = _FUNCTION_NAME_RE.match(function)
  if not m:
    return (function, "")
  return (m.group("name").strip(), (m.group("call") or "").strip())


def extract_backtrace_annotations(output):
  """Collect (function, location) tuples from raw debugger backtrace text."""
  annotations = []
  for line in output.splitlines():
    match = _BACKTRACE_ANNOTATION_LINE_RE.search(line)
    if not match:
      continue
    annotations.append(_normalize_annotation(match.group("annotation")))
  return annotations


def _strip_briefs(annotations):
  """Drop the `(...)` brief suffix from each annotation's function name."""
  return [(_split_function_and_call(func)[0], loc) for func, loc in annotations]


def check_backtrace(output, label, expected_annotations=None):
  """Check backtrace annotations against the expected function+location list.

  When the actual annotations include `(...)` briefs from
  V8_DEBUG_HELPER_FRAME_BRIEFS=1 (the default), the brief suffix is ignored
  here -- see `check_briefs_present` for separate brief-content assertions.
  """
  expected = (
      _DEFAULT_EXPECTED_ANNOTATIONS
      if expected_annotations is None else expected_annotations)
  found = _strip_briefs(extract_backtrace_annotations(output))
  expected_counter = Counter(expected)
  found_counter = Counter(found)
  missing = list((expected_counter - found_counter).elements())
  extras = list((found_counter - expected_counter).elements())
  if not missing and not extras:
    return None

  lines = [output, "\nFound normalized backtrace annotations:\n"]
  for annotation in found:
    lines.append(f"  {annotation}\n")
  if missing:
    lines.append(f"\nMissing {label} backtrace annotations:\n")
    for annotation in missing:
      lines.append(f"  {annotation}\n")
  if extras:
    lines.append(f"\nUnexpected {label} backtrace annotations:\n")
    for annotation in extras:
      lines.append(f"  {annotation}\n")
  return "".join(lines)


def check_briefs_present(output, label):
  """Assert that at least one frame annotation carries a `(...)` brief.

  Used in addition to `check_backtrace` to verify V8_DEBUG_HELPER_FRAME_BRIEFS
  default behaviour without locking the test against debug-helper's
  per-type wording.
  """
  for line in output.splitlines():
    match = _BACKTRACE_ANNOTATION_LINE_RE.search(line)
    if not match:
      continue
    function, _ = _normalize_annotation(match.group("annotation"))
    _, call_suffix = _split_function_and_call(function)
    if "this=" in call_suffix:
      return None
  return (f"{output}\n\nNo {label} backtrace annotation carried a "
          "`(this=...)` brief; was V8_DEBUG_HELPER_FRAME_BRIEFS=0 set?\n")
