# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run the LLDB bridge test and assert expected output."""

import argparse
import os
import subprocess
import sys

from check_annotations import check_frame_annotations, EXPECTED_FRAME_ANNOTATIONS


def run_lldb(args):
  """Launch LLDB in batch mode and return combined stdout+stderr."""
  env = os.environ.copy()
  env["V8_DEBUG_HELPER_LIB_PATH"] = os.path.abspath(args.debug_helper_lib)
  script_path = os.path.abspath(args.script)
  command = [
      args.lldb,
      "-b",
      "-O",
      f'command script import "{os.path.abspath(args.plugin)}"',
      "-O",
      f'target create "{os.path.abspath(args.d8)}"',
      "-O",
      f'settings set -- target.run-args --abort-on-uncaught-exception "{script_path}"',
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
  return completed.stdout + completed.stderr


def check_frame_annotation_test(output, script_path):
  """Verify that JS frame annotations are present in backtrace output."""
  script_name = os.path.basename(script_path)
  expected = EXPECTED_FRAME_ANNOTATIONS
  missing, found = check_frame_annotations(output, script_name, expected)
  if missing:
    sys.stderr.write(output)
    sys.stderr.write("\nParsed frame annotations:\n")
    for ann in found:
      sys.stderr.write(f"  {ann}\n")
    sys.stderr.write("\nMissing LLDB frame annotations: " +
                     ", ".join(map(str, missing)) + "\n")
    return False
  return True


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--lldb", default="lldb")
  parser.add_argument("--plugin", required=True)
  parser.add_argument("--d8", required=True)
  parser.add_argument("--script", required=True)
  parser.add_argument("--debug-helper-lib", required=True)
  args = parser.parse_args()

  output = run_lldb(args)
  ok = True

  if not check_frame_annotation_test(output, args.script):
    ok = False

  if ok:
    print("LLDB checks passed.")
  return 0 if ok else 1


if __name__ == "__main__":
  raise SystemExit(main())
