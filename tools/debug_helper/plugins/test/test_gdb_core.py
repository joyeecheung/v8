# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run the GDB bridge tests against prepared core files."""

import os
import unittest

from .helpers.backtrace import check_backtrace
from .helpers.corruptions import check_corruption
from .helpers.corruptions import get_corruption_cases
from .helpers.runtime import get_backtrace_core_path
from .helpers.runtime import get_corruption_core_path
from .helpers.runtime import get_gdb_core_test_config
from .helpers.runtime import run_debugger_command


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

  @classmethod
  def setUpClass(cls):
    cls.config = get_gdb_core_test_config()

  def test_backtrace(self):
    """Ensure the prepared backtrace core yields the expected annotations."""
    output = run_gdb_core(self.config, self.config.d8_binary,
                          get_backtrace_core_path(self.config))
    failure = check_backtrace(output, "GDB core")
    if failure is not None:
      self.fail(failure)


class GdbCoreCorruptionTest(unittest.TestCase):
  """Checks corruption-harness backtraces loaded from core files under GDB."""

  @classmethod
  def setUpClass(cls):
    cls.config = get_gdb_core_test_config()

  def test_corruption_cases(self):
    """Verify each prepared corruption core yields the expected trace."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    for case in get_corruption_cases(test_dir):
      with self.subTest(corruption=case["name"]):
        output = run_gdb_core(
            self.config, self.config.corruption_binary,
            get_corruption_core_path(self.config, case["name"]))
        failure = check_corruption(output, case, "GDB core")
        if failure is not None:
          self.fail(failure)


if __name__ == "__main__":
  unittest.main()
