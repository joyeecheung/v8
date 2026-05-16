# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run `v8 inspect` end-to-end under LLDB on a live d8 process."""

import os
import unittest

from .helpers.inspect import assert_contains_property
from .helpers.inspect import assert_inspect_shape
from .helpers.utils import get_lldb_live_test_config
from .helpers.utils import run_debugger_command

_LLDB_DRIVER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "helpers",
    "lldb_inspect_driver.py")


def run_lldb_inspect_live(config, binary_path, run_arguments):
  """Run d8 to the SIGABRT breakpoint and dispatch `v8 inspect` from there."""
  command = [
      config.debugger_binary,
      "-b",
      "-O",
      f'command script import "{os.path.abspath(config.plugin_path)}"',
      "-O",
      f'command script import "{_LLDB_DRIVER_PATH}"',
      "-O",
      f'target create "{os.path.abspath(binary_path)}"',
      "-O",
      f'settings set -- target.run-args {run_arguments}',
      "-O",
      "run",
      "-k",
      "v8dbg_test_inspect",
      "-k",
      "quit",
  ]
  return run_debugger_command(command, config.debug_helper_lib)


class LldbInspectTest(unittest.TestCase):
  """Inspect the receiver and first argument of test_func_3 from throw.js."""

  @classmethod
  def setUpClass(cls):
    cls.config = get_lldb_live_test_config()
    cls.backtrace_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "fixtures", "throw.js")

  def _split_sections(self, output):
    marker = "V8DBG_TEST: --- inspect "
    pieces = output.split(marker)
    sections = {"receiver": "", "jsobject_arg": ""}
    for piece in pieces[1:]:
      kind, _, body = piece.partition(" ---")
      sections[kind.strip()] = body
    return sections

  def test_inspect_receiver_and_jsobject_arg(self):
    output = run_lldb_inspect_live(
        self.config, self.config.d8_binary, '--abort-on-uncaught-exception '
        f'"{self.backtrace_script}"')
    self.assertIn("V8DBG_TEST: receiver=", output)
    sections = self._split_sections(output)

    receiver_failure = assert_inspect_shape(sections["receiver"],
                                            "LLDB receiver")
    if receiver_failure is not None:
      self.fail(receiver_failure)
    jsobject_arg_failure = assert_inspect_shape(sections["jsobject_arg"], "LLDB jsobject_arg")
    if jsobject_arg_failure is not None:
      self.fail(jsobject_arg_failure)
    receiver_map = assert_contains_property(sections["receiver"],
                                            "LLDB receiver", "map")
    if receiver_map is not None:
      self.fail(receiver_map)


if __name__ == "__main__":
  unittest.main()
