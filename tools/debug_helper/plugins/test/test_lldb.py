# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run the LLDB bridge test and assert JS frame annotations are present."""

import argparse
import os
import subprocess
import sys

from check_annotations import find_missing_annotations


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--lldb", default="lldb")
  parser.add_argument("--plugin", required=True)
  parser.add_argument("--d8", required=True)
  parser.add_argument("--script", required=True)
  parser.add_argument("--debug-helper-lib", required=True)
  args = parser.parse_args()

  env = os.environ.copy()
  env["V8_DEBUG_HELPER_LIB_PATH"] = os.path.abspath(args.debug_helper_lib)
  script_path = os.path.abspath(args.script)
  command = [
    args.lldb,
    "-b",
    "-O",
    f"command script import {os.path.abspath(args.plugin)}",
    "-O",
    f"target create {os.path.abspath(args.d8)}",
    "-O",
    f"settings set -- target.run-args --abort-on-uncaught-exception {script_path}",
    "-O",
    "run",
    "-k",
    "bt",
    "-k",
    "quit",
  ]
  completed = subprocess.run(
    command,
    capture_output=True,
    text=True,
    env=env,
    check=False,
  )
  output = completed.stdout + completed.stderr

  expected_annotations = (
    ("test_func_4", os.path.basename(script_path), 6, 7),
    ("test_func_3", os.path.basename(script_path), 6, 7),
    ("test_func_2", os.path.basename(script_path), 5, 21),
    ("test_func_1", os.path.basename(script_path), 1, 21),
  )
  missing, parsed_annotations = find_missing_annotations(
    output, expected_annotations)

  if missing:
    sys.stderr.write(output)
    sys.stderr.write("\nParsed annotations:\n")
    for annotation in parsed_annotations:
      sys.stderr.write(f"  {annotation}\n")
    sys.stderr.write(
      "\nMissing LLDB annotations: " + ", ".join(map(str, missing)) + "\n")
    return 1

  print("LLDB annotations verified.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())