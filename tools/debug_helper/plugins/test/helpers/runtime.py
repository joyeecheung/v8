# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Runtime configuration helpers for debugger plugin tests."""

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DebuggerTestConfig:
  debugger_binary: str
  plugin_path: str
  d8_binary: str
  corruption_binary: str
  debug_helper_lib: str
  gdbinit_path: Optional[str] = None
  core_dir: Optional[str] = None


def _require_env(name):
  """Load one required test setting from the environment."""
  value = os.environ.get(name)
  if not value:
    raise RuntimeError(f"Missing required environment variable: {name}")
  return value


def get_gdb_test_config():
  """Build the runtime config for the GDB test entry points."""
  return DebuggerTestConfig(
      debugger_binary=_require_env("GDB"),
      plugin_path=_require_env("GDB_PLUGIN"),
      d8_binary=_require_env("D8"),
      corruption_binary=_require_env("CORRUPTION_BIN"),
      debug_helper_lib=_require_env("DEBUG_HELPER_LIB"),
      gdbinit_path=_require_env("GDBINIT"),
  )


def get_lldb_test_config():
  """Build the runtime config for the LLDB test entry points."""
  return DebuggerTestConfig(
      debugger_binary=_require_env("LLDB"),
      plugin_path=_require_env("LLDB_PLUGIN"),
      d8_binary=_require_env("D8"),
      corruption_binary=_require_env("CORRUPTION_BIN"),
      debug_helper_lib=_require_env("DEBUG_HELPER_LIB"),
  )


def get_gdb_core_test_config():
  """Build the runtime config for the GDB core-file test entry points."""
  return DebuggerTestConfig(
      debugger_binary=_require_env("GDB"),
      plugin_path=_require_env("GDB_PLUGIN"),
      d8_binary=_require_env("D8"),
      corruption_binary=_require_env("CORRUPTION_BIN"),
      debug_helper_lib=_require_env("DEBUG_HELPER_LIB"),
      gdbinit_path=_require_env("GDBINIT"),
      core_dir=_require_env("CORE_DIR"),
  )


def get_lldb_core_test_config():
  """Build the runtime config for the LLDB core-file test entry points."""
  return DebuggerTestConfig(
      debugger_binary=_require_env("LLDB"),
      plugin_path=_require_env("LLDB_PLUGIN"),
      d8_binary=_require_env("D8"),
      corruption_binary=_require_env("CORRUPTION_BIN"),
      debug_helper_lib=_require_env("DEBUG_HELPER_LIB"),
      core_dir=_require_env("CORE_DIR"),
  )


def _require_core_dir(config):
  """Return the configured core directory or raise a helpful error."""
  if config.core_dir:
    return os.path.abspath(config.core_dir)
  raise RuntimeError("Missing core directory configuration")


def get_backtrace_core_path(config):
  """Return the path to the prepared d8 backtrace core file."""
  return os.path.join(_require_core_dir(config), "throw.core")


def get_corruption_core_path(config, case_name):
  """Return the path to one prepared corruption core file."""
  return os.path.join(_require_core_dir(config), f"{case_name}.core")


def run_debugger_command(command, debug_helper_lib):
  """Run one debugger command with the shared bridge library configured."""
  env = os.environ.copy()
  env["V8_DEBUG_HELPER_LIB_PATH"] = os.path.abspath(debug_helper_lib)
  completed = subprocess.run(
      command,
      capture_output=True,
      text=True,
      env=env,
      check=False,
  )
  output = completed.stdout + completed.stderr
  if completed.returncode != 0:
    raise RuntimeError(
        f"Debugger exited with code {completed.returncode}\n"
        f"Command: {' '.join(command)}\n"
        f"Output:\n{output}")
  return output
