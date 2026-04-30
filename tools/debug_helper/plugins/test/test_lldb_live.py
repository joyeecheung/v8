# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run the LLDB bridge tests and assert expected output."""

import os
import unittest

from .helpers.backtrace import assert_live_backtrace
from .helpers.corruptions import assert_live_corruption_cases
from .helpers.utils import get_lldb_live_test_config
from .helpers.utils import run_debugger_command


def run_lldb_live(config, binary_path, run_arguments):
  """Run one LLDB backtrace command and return its combined text output."""
  command = [
      config.debugger_binary,
      "-b",
      "-O",
      f'command script import "{os.path.abspath(config.plugin_path)}"',
      "-O",
      f'target create "{os.path.abspath(binary_path)}"',
      "-O",
      f'settings set -- target.run-args {run_arguments}',
      "-O",
      "run",
      "-k",
      "bt",
      "-k",
      "quit",
  ]
  return run_debugger_command(command, config.debug_helper_lib)


class LldbBacktraceTest(unittest.TestCase):
  """Checks the normal d8 throw.js backtrace under LLDB."""

  debugger_name = "LLDB"

  @classmethod
  def get_config(cls):
    return get_lldb_live_test_config()

  @staticmethod
  def run_debugger(config, binary_path, argument):
    return run_lldb_live(config, binary_path, argument)

  @classmethod
  def setUpClass(cls):
    cls.config = cls.get_config()

  def test_backtrace(self):
    """Ensure the regular nested JS backtrace is annotated as expected."""
    assert_live_backtrace(self, __file__, self.debugger_name, self.config,
                          self.run_debugger)


class LldbCorruptionTest(unittest.TestCase):
  """Checks corruption-harness backtraces under LLDB."""

  debugger_name = "LLDB"

  @classmethod
  def get_config(cls):
    return get_lldb_live_test_config()

  @staticmethod
  def run_debugger(config, binary_path, argument):
    return run_lldb_live(config, binary_path, argument)

  @classmethod
  def setUpClass(cls):
    cls.config = cls.get_config()

  def test_corruption_cases(self):
    """Verify each corruption case yields the expected trace."""
    assert_live_corruption_cases(self, __file__, self.debugger_name,
                                 self.config, self.run_debugger)


if __name__ == "__main__":
  unittest.main()
