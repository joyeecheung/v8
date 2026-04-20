# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LLDB integration for the V8 debugger bridge."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from debugger_bridge import frame_suffix


_DEFAULT_FRAME_FORMAT = (
  "frame #${frame.index}:{ ${frame.no-debug}${frame.pc}}"
  "{ ${module.file.basename}{`${function.name-with-args}"
  "{${frame.no-debug}${function.pc-offset}}}}"
  "{ at ${line.file.basename}:${line.number}}"
  "{${function.is-optimized} [opt]}"
)


def frame_annotation(frame, _unused):
  try:
    function_name = frame.GetFunctionName()
    if not function_name:
      symbol = frame.GetSymbol()
      if symbol and symbol.IsValid():
        function_name = symbol.GetName() or ""
    if "Builtin" not in function_name:
      return ""

    process = frame.GetThread().GetProcess()

    def read_memory(address, byte_count):
      error = __import__("lldb").SBError()
      data = process.ReadMemory(address, byte_count, error)
      if not error.Success():
        raise RuntimeError(error.GetCString() or "unable to read memory")
      return data

    return frame_suffix(
      frame.GetFP(), read_memory)
  except Exception:
    return ""


def __lldb_init_module(debugger, internal_dict):
  del internal_dict
  callback = f"${{script.frame:{__name__}.frame_annotation}}"
  debugger.HandleCommand(
    f"settings set frame-format '{_DEFAULT_FRAME_FORMAT}{callback}\\n'")
