# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Run `v8 inspect` end-to-end under LLDB on a live d8 process."""

import os
import unittest

from .helpers.inspect import (
    check_inspect_receiver,
    check_inspect_recurses_into_map,
)
from .helpers.session import LldbSession
from .helpers.utils import get_lldb_live_test_config


class LldbInspectLiveTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.config = get_lldb_live_test_config()
    cls.script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "fixtures",
        "inspect-fixture.js")

  def _session(self):
    return LldbSession(
        lldb_binary=self.config.debugger_binary,
        target_binary=self.config.d8_binary,
        plugin_path=self.config.plugin_path,
        target_args=f'--abort-on-uncaught-exception "{self.script}"',
        env={"V8_DEBUG_HELPER_LIB_PATH": self.config.debug_helper_lib},
    )

  def test_inspect_receiver(self):
    """Inspect the Greeter receiver at SIGABRT."""
    with self._session() as session:
      session.run_to_abort()
      check_inspect_receiver(session)

  def test_inspect_recurses_into_map(self):
    """Follow the receiver's `.map` address and inspect the Map."""
    with self._session() as session:
      session.run_to_abort()
      check_inspect_recurses_into_map(session)


if __name__ == "__main__":
  unittest.main()
