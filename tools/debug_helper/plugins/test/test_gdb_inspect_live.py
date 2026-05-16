# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run `v8 inspect` end-to-end under GDB on a live d8 process."""

import os
import unittest

from .helpers.inspect import assert_contains_property
from .helpers.inspect import assert_inspect_shape
from .helpers.utils import get_gdb_live_test_config
from .helpers.utils import run_debugger_command

_GDB_PY_DRIVER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "helpers", "inspect_driver.py")


def run_gdb_inspect_live(config, binary_path, run_arguments):
  """Run d8 to the SIGABRT breakpoint and dispatch `v8 inspect` from there."""
  command = [
      config.debugger_binary,
      "-nx",
      "-q",
      "-batch",
      "-iex",
      "set debuginfod enabled off",
      "-iex",
      f"source {os.path.abspath(config.gdbinit_path)}",
      "-iex",
      f"source {os.path.abspath(config.plugin_path)}",
      "-ex",
      f"file {os.path.abspath(binary_path)}",
      "-ex",
      f"run {run_arguments}",
      "-ex",
      f"source {_GDB_PY_DRIVER_PATH}",
      "-ex",
      "quit",
  ]
  return run_debugger_command(command, config.debug_helper_lib)


class GdbInspectTest(unittest.TestCase):
  """Inspect the receiver and first argument of test_func_3 from throw.js."""

  @classmethod
  def setUpClass(cls):
    cls.config = get_gdb_live_test_config()
    cls.backtrace_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "fixtures", "throw.js")

  def _split_sections(self, output):
    """Split the gdb output into receiver and jsobject_arg inspect sections."""
    marker = "V8DBG_TEST: --- inspect "
    pieces = output.split(marker)
    sections = {"receiver": "", "jsobject_arg": ""}
    for piece in pieces[1:]:
      kind, _, body = piece.partition(" ---")
      sections[kind.strip()] = body
    return sections

  def test_inspect_receiver_and_jsobject_arg(self):
    """Ensure both receiver and first argument render with full briefs."""
    output = run_gdb_inspect_live(
        self.config, self.config.d8_binary, '--abort-on-uncaught-exception '
        f'"{self.backtrace_script}"')
    self.assertIn("V8DBG_TEST: receiver=", output)
    sections = self._split_sections(output)

    receiver_failure = assert_inspect_shape(sections["receiver"],
                                            "GDB receiver")
    if receiver_failure is not None:
      self.fail(receiver_failure)

    jsobject_arg_failure = assert_inspect_shape(sections["jsobject_arg"], "GDB jsobject_arg")
    if jsobject_arg_failure is not None:
      self.fail(jsobject_arg_failure)

    # The receiver is JSGlobalProxy; it has a `.map=` property.
    receiver_map = assert_contains_property(sections["receiver"], "GDB receiver",
                                            "map")
    if receiver_map is not None:
      self.fail(receiver_map)


if __name__ == "__main__":
  unittest.main()
