# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run the GDB bridge tests against prepared core files."""

import os
import unittest

from .helpers.backtrace import assert_core_backtrace
from .helpers.corruptions import assert_core_corruption_cases
from .helpers.utils import get_gdb_core_test_config
from .helpers.utils import run_debugger_command


def run_gdb_core(config, binary_path, core_path):
  """Run one GDB backtrace command against a prepared core file."""
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
      f"core-file {os.path.abspath(core_path)}",
      "-ex",
      "bt",
      "-ex",
      "quit",
  ]
  return run_debugger_command(command, config.debug_helper_lib)


class GdbCoreBacktraceTest(unittest.TestCase):
  """Checks the d8 throw fixture backtrace loaded from a core file."""

  debugger_name = "GDB core"

  @classmethod
  def get_config(cls):
    return get_gdb_core_test_config()

  @staticmethod
  def run_debugger(config, binary_path, argument):
    return run_gdb_core(config, binary_path, argument)

  @classmethod
  def setUpClass(cls):
    cls.config = cls.get_config()

  def test_backtrace(self):
    """Ensure the prepared backtrace core yields the expected annotations."""
    assert_core_backtrace(self, self.debugger_name, self.config,
                          self.run_debugger)


class GdbCoreCorruptionTest(unittest.TestCase):
  """Checks corruption-harness backtraces loaded from core files under GDB."""

  debugger_name = "GDB core"

  @classmethod
  def get_config(cls):
    return get_gdb_core_test_config()

  @staticmethod
  def run_debugger(config, binary_path, argument):
    return run_gdb_core(config, binary_path, argument)

  @classmethod
  def setUpClass(cls):
    cls.config = cls.get_config()

  def test_corruption_cases(self):
    """Verify each prepared corruption core yields the expected trace."""
    assert_core_corruption_cases(self, __file__, self.debugger_name,
                                 self.config, self.run_debugger)


if __name__ == "__main__":
  unittest.main()
