# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run `v8 inspect` end-to-end under GDB on a prepared core file."""

import os
import unittest

from .helpers.inspect import assert_contains_property
from .helpers.inspect import assert_inspect_shape
from .helpers.utils import get_gdb_core_test_config
from .helpers.utils import run_debugger_command
from .test_gdb_inspect_live import _GDB_PY_DRIVER_PATH


def run_gdb_inspect_core(config, binary_path, core_path):
  """Load a prepared core and dispatch `v8 inspect` from the JS frame."""
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
      f"source {_GDB_PY_DRIVER_PATH}",
      "-ex",
      "quit",
  ]
  return run_debugger_command(command, config.debug_helper_lib)


class GdbInspectCoreTest(unittest.TestCase):
  """Inspect the receiver/jsobject_arg of test_func_3 from the prepared core file."""

  @classmethod
  def setUpClass(cls):
    cls.config = get_gdb_core_test_config()
    assert cls.config.core_dir is not None
    cls.core_dir = os.path.abspath(cls.config.core_dir)

  def test_inspect_receiver_and_jsobject_arg(self):
    """Ensure inspect output survives the live/core boundary."""
    output = run_gdb_inspect_core(self.config, self.config.d8_binary,
                                  os.path.join(self.core_dir, "throw.core"))
    self.assertIn("V8DBG_TEST: receiver=", output)
    marker = "V8DBG_TEST: --- inspect "
    pieces = output.split(marker)
    sections = {"receiver": "", "jsobject_arg": ""}
    for piece in pieces[1:]:
      kind, _, body = piece.partition(" ---")
      sections[kind.strip()] = body

    receiver_failure = assert_inspect_shape(sections["receiver"],
                                            "GDB core receiver")
    if receiver_failure is not None:
      self.fail(receiver_failure)
    jsobject_arg_failure = assert_inspect_shape(sections["jsobject_arg"], "GDB core jsobject_arg")
    if jsobject_arg_failure is not None:
      self.fail(jsobject_arg_failure)
    receiver_map = assert_contains_property(sections["receiver"],
                                            "GDB core receiver", "map")
    if receiver_map is not None:
      self.fail(receiver_map)


if __name__ == "__main__":
  unittest.main()
