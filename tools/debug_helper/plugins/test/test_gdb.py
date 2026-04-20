# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run the GDB bridge test and assert JS frame annotations are present."""

import argparse
import os
import subprocess
import sys

from check_annotations import find_missing_annotations


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--gdb", default="gdb")
  parser.add_argument("--gdbinit", required=True)
  parser.add_argument("--plugin", required=True)
  parser.add_argument("--d8", required=True)
  parser.add_argument("--script", required=True)
  parser.add_argument("--debug-helper-lib", required=True)
  args = parser.parse_args()

  env = os.environ.copy()
  env["V8_DEBUG_HELPER_LIB_PATH"] = os.path.abspath(args.debug_helper_lib)
  script_path = os.path.abspath(args.script)
  command = [
    args.gdb,
    "-nx",
    "-q",
    "-batch",
    "-iex",
    "set debuginfod enabled off",
    "-iex",
    f"source {os.path.abspath(args.gdbinit)}",
    "-iex",
    f"source {os.path.abspath(args.plugin)}",
    "-ex",
    f"file {os.path.abspath(args.d8)}",
    "-ex",
    f"run --abort-on-uncaught-exception {script_path}",
    "-ex",
    "bt",
    "-ex",
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
      "\nMissing GDB annotations: " + ", ".join(map(str, missing)) + "\n")
    return 1

  print("GDB annotations verified.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())