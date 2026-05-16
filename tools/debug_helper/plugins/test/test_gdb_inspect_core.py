# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run `v8 inspect` end-to-end under GDB on a prepared core file."""

import os
import unittest

from .helpers.inspect import (
    check_inspect_receiver,
    check_inspect_recurses_into_map,
)
from .helpers.session import GdbSession
from .helpers.utils import get_gdb_core_test_config


class GdbInspectCoreTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.config = get_gdb_core_test_config()
    assert cls.config.core_dir is not None
    cls.core_path = os.path.join(os.path.abspath(cls.config.core_dir),
                                 "inspect-fixture.core")

  def _session(self):
    return GdbSession(
        gdb_binary=self.config.debugger_binary,
        target_binary=self.config.d8_binary,
        plugin_path=self.config.plugin_path,
        gdbinit_path=self.config.gdbinit_path,
        core_path=self.core_path,
        env={"V8_DEBUG_HELPER_LIB_PATH": self.config.debug_helper_lib},
    )

  def test_inspect_receiver(self):
    """Inspect the Greeter receiver from the core."""
    with self._session() as session:
      check_inspect_receiver(session)

  def test_inspect_recurses_into_map(self):
    """Follow the receiver's `.map` address and inspect the Map."""
    with self._session() as session:
      check_inspect_recurses_into_map(session)


if __name__ == "__main__":
  unittest.main()
