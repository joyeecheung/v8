# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run the LLDB bridge tests against prepared core files."""

import os
import unittest

from .helpers.backtrace import check_backtrace
from .helpers.corruptions import check_corruption
from .helpers.corruptions import get_corruption_cases
from .helpers.runtime import get_backtrace_core_path
from .helpers.runtime import get_corruption_core_path
from .helpers.runtime import get_lldb_core_test_config
from .helpers.runtime import run_debugger_command


def run_lldb_core(config, binary_path, core_path):
  """Run one LLDB backtrace command against a prepared core file."""
  command = [
      config.debugger_binary,
      "-b",
      "-O",
      f'command script import "{os.path.abspath(config.plugin_path)}"',
      "-O",
      f'target create --core "{os.path.abspath(core_path)}" '
      f'"{os.path.abspath(binary_path)}"',
      "-O",
      "bt",
      "-O",
      "quit",
  ]
  return run_debugger_command(command, config.debug_helper_lib)


class LldbCoreBacktraceTest(unittest.TestCase):
  """Checks the d8 throw fixture backtrace loaded from a core file."""

  @classmethod
  def setUpClass(cls):
    cls.config = get_lldb_core_test_config()

  def test_backtrace(self):
    """Ensure the prepared backtrace core yields the expected annotations."""
    output = run_lldb_core(self.config, self.config.d8_binary,
                           get_backtrace_core_path(self.config))
    failure = check_backtrace(output, "LLDB core")
    if failure is not None:
      self.fail(failure)


class LldbCoreCorruptionTest(unittest.TestCase):
  """Checks corruption-harness backtraces loaded from core files under LLDB."""

  @classmethod
  def setUpClass(cls):
    cls.config = get_lldb_core_test_config()

  def test_corruption_cases(self):
    """Verify each prepared corruption core yields the expected trace."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    for case in get_corruption_cases(test_dir):
      with self.subTest(corruption=case["name"]):
        output = run_lldb_core(
            self.config, self.config.corruption_binary,
            get_corruption_core_path(self.config, case["name"]))
        failure = check_corruption(output, case, "LLDB core")
        if failure is not None:
          self.fail(failure)


if __name__ == "__main__":
  unittest.main()
