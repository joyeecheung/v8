# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run the GDB bridge test and assert expected output."""

import argparse
import os
import subprocess
import sys

from check_annotations import check_frame_annotations


def run_gdb(args):
  """Launch GDB in batch mode and return combined stdout+stderr."""
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
  return completed.stdout + completed.stderr


def check_frame_annotation_test(output, script_path):
  """Verify that JS frame annotations are present in backtrace output."""
  script_name = os.path.basename(script_path)
  expected = (
      ("test_func_3", 15, 1),
      ("<anonymous>", 10, 11),
      ("test_func_2", 9, 1),
      ("test_func_1", 5, 1),
      ("<anonymous>", 1, 1),
  )
  missing, found = check_frame_annotations(output, script_name, expected)
  if missing:
    sys.stderr.write(output)
    sys.stderr.write("\nParsed frame annotations:\n")
    for ann in found:
      sys.stderr.write(f"  {ann}\n")
    sys.stderr.write("\nMissing GDB frame annotations: " +
                     ", ".join(map(str, missing)) + "\n")
    return False
  return True


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--gdb", default="gdb")
  parser.add_argument("--gdbinit", required=True)
  parser.add_argument("--plugin", required=True)
  parser.add_argument("--d8", required=True)
  parser.add_argument("--script", required=True)
  parser.add_argument("--debug-helper-lib", required=True)
  args = parser.parse_args()

  output = run_gdb(args)
  ok = True

  if not check_frame_annotation_test(output, args.script):
    ok = False

  if ok:
    print("GDB checks passed.")
  return 0 if ok else 1


if __name__ == "__main__":
  raise SystemExit(main())
