# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run the GDB bridge tests and assert expected output."""

import os
import unittest

from .helpers.backtrace import assert_live_backtrace
from .helpers.corruptions import assert_live_corruption_cases
from .helpers.utils import get_gdb_live_test_config
from .helpers.utils import run_debugger_command


def run_gdb_live(config, binary_path, run_arguments):
  """Run one GDB backtrace command and return its combined text output."""
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
      "bt",
      "-ex",
      "quit",
  ]
  return run_debugger_command(command, config.debug_helper_lib)


class GdbBacktraceTest(unittest.TestCase):
  """Checks the normal d8 throw fixture backtrace under GDB."""

  debugger_name = "GDB"

  @classmethod
  def get_config(cls):
    return get_gdb_live_test_config()

  @staticmethod
  def run_debugger(config, binary_path, argument):
    return run_gdb_live(config, binary_path, argument)

  @classmethod
  def setUpClass(cls):
    cls.config = cls.get_config()

  def test_backtrace(self):
    """Ensure the regular nested JS backtrace is annotated as expected."""
    assert_live_backtrace(self, __file__, self.debugger_name, self.config,
                          self.run_debugger)


class GdbCorruptionTest(unittest.TestCase):
  """Checks corruption-harness backtraces under GDB."""

  debugger_name = "GDB"

  @classmethod
  def get_config(cls):
    return get_gdb_live_test_config()

  @staticmethod
  def run_debugger(config, binary_path, argument):
    return run_gdb_live(config, binary_path, argument)

  @classmethod
  def setUpClass(cls):
    cls.config = cls.get_config()

  def test_corruption_cases(self):
    """Verify each corruption case yields the expected trace."""
    assert_live_corruption_cases(self, __file__, self.debugger_name,
                                 self.config, self.run_debugger)


if __name__ == "__main__":
  unittest.main()
