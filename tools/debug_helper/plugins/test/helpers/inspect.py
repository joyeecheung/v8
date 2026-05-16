# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Helpers for `v8 inspect` integration tests.

Pulls the receiver and first-argument tagged pointers from a JS frame at the
SIGABRT breakpoint and asserts that the `v8 inspect` rendering follows the
expected `0xADDR:<Type {...}>` grammar.
"""

import re

# `v8 inspect <receiver>` head: address followed by an angle-bracket brief.
_HEAD_RE = re.compile(r"0x[0-9a-f]+:<[^>]")
# A property line inside the brief body.
_PROPERTY_LINE_RE = re.compile(r"\s*\.[A-Za-z_][A-Za-z0-9_]*=")


def assert_inspect_shape(output, label):
  """Return None if `output` contains a well-formed `v8 inspect` block."""
  if not _HEAD_RE.search(output):
    return (f"{output}\n\nNo {label} `v8 inspect` head "
            "(0xADDR:<Type {...}) found in output\n")
  if not _PROPERTY_LINE_RE.search(output):
    return (f"{output}\n\nNo {label} `v8 inspect` property entries "
            "(e.g. `.map=...`) found in output\n")
  if "}>" not in output:
    return (f"{output}\n\nNo {label} `v8 inspect` end-of-body marker `}}>` "
            "found in output\n")
  return None


def assert_contains_property(output, label, prop_name):
  """Return None if `output` contains a `.prop_name=` entry."""
  if re.search(rf"\.{re.escape(prop_name)}=", output):
    return None
  return (f"{output}\n\nMissing `{label}` property `.{prop_name}=` "
          "in v8 inspect output\n")


def assert_inspect_failure_shape(output, label):
  """Return None if `output` reports an inaccessible-Map fallback."""
  if "[Map inaccessible]" not in output and "[Map pointer invalid]" not in output:
    return (f"{output}\n\nExpected `{label}` v8 inspect to report a "
            "Map-access failure brief\n")
  if "could be one of" not in output:
    return (f"{output}\n\nExpected `{label}` v8 inspect to print "
            "`could be one of` footer for guessed types\n")
  return None
