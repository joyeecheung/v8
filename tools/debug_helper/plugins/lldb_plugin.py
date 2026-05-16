# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""LLDB integration for the V8 debugger bridge."""

import io
import os
import shlex
import traceback

import lldb

from v8dbg.dispatch import dispatch_v8_command
from v8dbg.shared_bridge import DebuggerBridge

_VERBOSE = os.environ.get("V8_DEBUG_HELPER_VERBOSE", "") != ""
_bridges = {}


def _get_bridge(ptr_size):
  """Cache one bridge per target pointer size."""
  if ptr_size not in _bridges:
    _bridges[ptr_size] = DebuggerBridge(ptr_size=ptr_size)
  return _bridges[ptr_size]


_DEFAULT_FRAME_FORMAT = ("frame #${frame.index}:{ ${frame.no-debug}${frame.pc}}"
                         "{ ${module.file.basename}{`${function.name-with-args}"
                         "{${frame.no-debug}${function.pc-offset}}}}"
                         "{ at ${line.file.basename}:${line.number}}"
                         "{${function.is-optimized} [opt]}")


def _make_read_memory(process):
  """Return a memory-read callback bound to one lldb process."""

  def read_memory(address, byte_count):
    error = lldb.SBError()
    data = process.ReadMemory(address, byte_count, error)
    if not error.Success():
      raise RuntimeError(error.GetCString() or "unable to read memory")
    return data

  return read_memory


class _LldbHintsResolver:
  """Adapter from the shared bridge's HeapHintsResolver protocol to lldb."""

  def __init__(self, target, process):
    self._target = target
    self._process = process
    self._ptr_size = target.GetAddressByteSize() if target else 8

  def read_pointer(self, addr):
    if not self._process:
      return None
    error = lldb.SBError()
    data = self._process.ReadMemory(addr, self._ptr_size, error)
    if not error.Success() or not data or len(data) != self._ptr_size:
      return None
    return int.from_bytes(data, "little", signed=False)

  def global_symbol_address(self, name):
    if not self._target:
      return None
    try:
      values = self._target.FindGlobalVariables(name, 1)
    except Exception:
      values = None
    if values and values.GetSize() > 0:
      var = values.GetValueAtIndex(0)
      if var and var.IsValid():
        load_addr = var.GetLoadAddress()
        if load_addr != lldb.LLDB_INVALID_ADDRESS:
          return int(load_addr)
    # TLS fallback: GetLoadAddress on a thread_local returns the template,
    # not the per-thread address.
    value = self._target.EvaluateExpression(f"&'{name}'")
    if value is None or not value.IsValid():
      return None
    err = value.GetError()
    if err and not err.Success():
      return None
    try:
      addr = int(value.GetValueAsUnsigned())
    except Exception:
      return None
    return addr or None

  def field_offset(self, type_name, field_name):
    if not self._target:
      return None
    try:
      sb_type = self._target.FindFirstType(type_name)
    except Exception:
      return None
    if not sb_type or not sb_type.IsValid():
      return None
    for i in range(sb_type.GetNumberOfFields()):
      field = sb_type.GetFieldAtIndex(i)
      if field.GetName() == field_name:
        return int(field.GetOffsetInBytes())
    return None


def _evaluate_address_in_lldb(target, frame, text):
  """Evaluate a debugger expression as an integer address, or None on failure."""
  if frame and frame.IsValid():
    value = frame.EvaluateExpression(text)
  elif target and target.IsValid():
    value = target.EvaluateExpression(text)
  else:
    return None
  if value is None or not value.IsValid():
    return None
  err = value.GetError()
  if not err or not err.Success():
    return None
  # Sentinel distinguishes a real Smi 0 from a silent conversion failure.
  fail_value = (1 << 64) - 1
  try:
    raw = value.GetValueAsUnsigned(fail_value)
  except Exception:
    return None
  if raw == fail_value:
    return None
  return int(raw)


def frame_annotation(frame, _unused):
  """Return the V8 JS suffix for one LLDB frame, or an empty string."""
  try:
    function_name = frame.GetFunctionName()
    if not function_name:
      symbol = frame.GetSymbol()
      if symbol and symbol.IsValid():
        function_name = symbol.GetName() or ""
    if function_name and "Builtin" not in function_name:
      return ""

    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    read_memory = _make_read_memory(process)

    fp = frame.GetFP()
    if fp == lldb.LLDB_INVALID_ADDRESS:
      return ""
    ptr_size = target.GetAddressByteSize()
    bridge = _get_bridge(ptr_size)
    return bridge.frame_suffix(fp, read_memory)
  except Exception:
    if _VERBOSE:
      traceback.print_exc()
    return ""


def cmd_v8(debugger, command, result, _internal_dict):
  """`v8 <subcommand> ...` dispatcher entry point for LLDB."""
  try:
    argv = shlex.split(command or "")
  except ValueError:
    argv = (command or "").split()
  target = debugger.GetSelectedTarget()
  process = target.GetProcess() if target else None
  frame = None
  if process:
    thread = process.GetSelectedThread()
    if thread:
      frame = thread.GetSelectedFrame()

  if not process or not process.IsValid():
    result.SetError("v8: no running process / loaded core to inspect")
    return

  ptr_size = target.GetAddressByteSize()
  bridge = _get_bridge(ptr_size)
  buffer = io.StringIO()

  read_memory = _make_read_memory(process)

  def eval_address(text):
    return _evaluate_address_in_lldb(target, frame, text)

  try:
    dispatch_v8_command(
        bridge,
        argv,
        buffer,
        read_memory=read_memory,
        eval_address=eval_address,
        hints_resolver=_LldbHintsResolver(target, process),
    )
  except Exception:
    if _VERBOSE:
      traceback.print_exc()
      result.SetError("v8: command failed")
    else:
      result.SetError(
          "v8: command failed; rerun with V8_DEBUG_HELPER_VERBOSE=1")
    return
  text = buffer.getvalue()
  if text:
    result.AppendMessage(text.rstrip("\n"))


def __lldb_init_module(debugger, _internal_dict):
  """Hook the LLDB frame format and register the `v8` command."""
  if not os.environ.get("V8_DEBUG_HELPER_LIB_PATH"):
    print(
        "v8: V8_DEBUG_HELPER_LIB_PATH is not set; the `v8` command and "
        "JS frame annotations will not be registered. Set it to the "
        "libv8_debug_helper shared library and re-import this plugin.")
    return
  callback = f"${{script.frame:{__name__}.frame_annotation}}"
  debugger.HandleCommand(
      f"settings set frame-format '{_DEFAULT_FRAME_FORMAT}{callback}\\n'")
  debugger.HandleCommand(f"command script add -f {__name__}.cmd_v8 v8")
