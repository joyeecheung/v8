# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""GDB python driver sourced by the inspect integration tests.

Walks the thread's frame chain to find the deepest `InterpreterEntryTrampoline`
frame (i.e. the active JS frame at the SIGABRT). Reads the receiver and the
first user argument from that frame's standard JS slots and dispatches
`v8 inspect <addr>` for both. Output is prefixed with the V8DBG_TEST marker so
the test runner can extract the per-target sections.
"""

import gdb


def _walk_to_js_frame():
  frame = gdb.newest_frame()
  while frame is not None:
    name = frame.name() or ""
    if "InterpreterEntryTrampoline" in name:
      return frame
    frame = frame.older()
  return None


def run():
  js_frame = _walk_to_js_frame()
  if js_frame is None:
    print("V8DBG_TEST: no JS frame found")
    return
  js_frame.select()
  fp = int(gdb.parse_and_eval("$rbp"))
  inferior = gdb.selected_inferior()
  receiver = int.from_bytes(
      bytes(inferior.read_memory(fp + 16, 8)), "little")
  # arg2 of test_func_3 in fixtures/throw.js is the JSObject `{inner: o}` --
  # picked because it is guaranteed to be a non-Smi value with inspectable
  # children, unlike the leading Smi/Oddball args.
  jsobject_arg = int.from_bytes(
      bytes(inferior.read_memory(fp + 16 + 3 * 8, 8)), "little")
  print(f"V8DBG_TEST: receiver=0x{receiver:x}")
  print(f"V8DBG_TEST: jsobject_arg=0x{jsobject_arg:x}")
  print("V8DBG_TEST: --- inspect receiver ---")
  gdb.execute(f"v8 inspect 0x{receiver:x}")
  print("V8DBG_TEST: --- inspect jsobject_arg ---")
  gdb.execute(f"v8 inspect 0x{jsobject_arg:x}")


run()
