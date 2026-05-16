# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""LLDB python driver loaded by the inspect integration tests.

Mirror of helpers/inspect_driver.py for lldb: walks the thread's frame chain
to find the JS frame, reads its receiver and first user argument at the
standard JS-frame offsets, and dispatches `v8 inspect <addr>` for each.
"""

import lldb


def _walk_to_js_frame(thread):
  for frame in thread.frames:
    name = frame.GetFunctionName() or ""
    if "InterpreterEntryTrampoline" in name:
      return frame
  return None


def _run_v8_inspect(debugger, addr):
  """Capture `v8 inspect <addr>` output inline so it interleaves with prints.

  lldb's HandleCommand flushes its own buffer separately from Python's
  stdout, which scrambles relative ordering. Routing the command through
  SBCommandInterpreter with an explicit return object lets us print the
  captured output in the same stream as the V8DBG_TEST markers.
  """
  result = lldb.SBCommandReturnObject()
  interp = debugger.GetCommandInterpreter()
  interp.HandleCommand(f"v8 inspect 0x{addr:x}", result)
  if result.GetOutput():
    print(result.GetOutput(), end="")
    if not result.GetOutput().endswith("\n"):
      print()
  if result.GetError():
    print(result.GetError(), end="")


def run(debugger, _command, _result, _internal_dict):
  target = debugger.GetSelectedTarget()
  process = target.GetProcess()
  thread = process.GetSelectedThread()
  js_frame = _walk_to_js_frame(thread)
  if js_frame is None:
    print("V8DBG_TEST: no JS frame found")
    return
  fp = int(js_frame.GetFP())
  err = lldb.SBError()
  receiver = int.from_bytes(
      process.ReadMemory(fp + 16, 8, err), "little")
  # arg2 of test_func_3 in fixtures/throw.js is the JSObject `{inner: o}` --
  # picked because it is guaranteed to be a non-Smi value with inspectable
  # children, unlike the leading Smi/Oddball args.
  jsobject_arg = int.from_bytes(
      process.ReadMemory(fp + 16 + 3 * 8, 8, err), "little")
  print(f"V8DBG_TEST: receiver=0x{receiver:x}")
  print(f"V8DBG_TEST: jsobject_arg=0x{jsobject_arg:x}")
  print("V8DBG_TEST: --- inspect receiver ---")
  _run_v8_inspect(debugger, receiver)
  print("V8DBG_TEST: --- inspect jsobject_arg ---")
  _run_v8_inspect(debugger, jsobject_arg)


def __lldb_init_module(debugger, _internal_dict):
  debugger.HandleCommand(
      f"command script add -f {__name__}.run v8dbg_test_inspect")
