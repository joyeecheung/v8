# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""GDB integration for the V8 debugger bridge."""

# GDB does not add the directory of the current script to the module
# search path, so we need to do it ourselves to load the shared bridge.
import io
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gdb
from gdb.FrameDecorator import FrameDecorator

from shared_bridge import DebuggerBridge

_VERBOSE = os.environ.get("V8_DEBUG_HELPER_VERBOSE", "") != ""
_bridges = {}


def _get_bridge(ptr_size):
  """Cache one bridge per target pointer size."""
  if ptr_size not in _bridges:
    _bridges[ptr_size] = DebuggerBridge(ptr_size=ptr_size)
  return _bridges[ptr_size]


def _read_memory_callback(address, byte_count):
  """Read target memory through the currently selected inferior."""
  return bytes(gdb.selected_inferior().read_memory(address, byte_count))


def _ptr_size():
  """Best-effort target pointer size."""
  try:
    return gdb.lookup_type("void").pointer().sizeof
  except Exception:
    return None


class _GdbHintsResolver:
  """Adapter from the shared bridge's HeapHintsResolver protocol to gdb."""

  def read_pointer(self, addr):
    ptr_size = _ptr_size() or 8
    try:
      data = bytes(gdb.selected_inferior().read_memory(addr, ptr_size))
    except Exception:
      return None
    if len(data) != ptr_size:
      return None
    return int.from_bytes(data, "little", signed=False)

  def global_symbol_address(self, name):
    try:
      sym = gdb.lookup_global_symbol(name)
      if sym is None:
        return None
      value = sym.value()
      addr = value.address
      if addr is None:
        # Thread-locals: try `&name` via parse_and_eval (gdb resolves TLS for
        # the selected thread).
        addr = gdb.parse_and_eval(f"&'{name}'")
      if addr is None:
        return None
      return int(addr)
    except Exception:
      return None

  def field_offset(self, type_name, field_name):
    try:
      t = gdb.lookup_type(type_name)
    except Exception:
      return None
    try:
      field = t[field_name]
    except Exception:
      return None
    bitpos = getattr(field, "bitpos", None)
    if bitpos is None:
      return None
    return int(bitpos) // 8


def _evaluate_address_in_gdb(text):
  """Evaluate a debugger expression as an integer address."""
  try:
    return int(gdb.parse_and_eval(text))
  except Exception:
    return None


class V8DbgFrameDecorator(FrameDecorator):
  """Appends V8 JS frame annotations to backtraces."""

  def __init__(self, frame_obj):
    super().__init__(frame_obj)

  def function(self):
    """Keep the native frame name when it is useful, else append JS context."""
    base_name = super().function()
    frame = self.inferior_frame()
    if not base_name:
      try:
        base_name = frame.name() or ""
      except Exception:
        if _VERBOSE:
          traceback.print_exc()
        base_name = ""
    # TODO(joyee): "Builtin" substring check is a coarse heuristic for
    # detecting JS-bridge frames whose native name should not suppress the
    # JS annotation; it can also match unrelated builtins with JS-y names.
    # Refine this when we have a robust way to identify V8 trampoline frames.
    if base_name and "Builtin" not in base_name:
      return base_name
    frame_pointer = 0
    # Extend this register list as the plugin grows support for more
    # architectures. Today the tested targets are x64 and arm64.
    for register_name in ("rbp", "fp", "x29"):
      try:
        value = frame.read_register(register_name)
      except Exception:
        continue
      try:
        frame_pointer = int(value)
      except Exception:
        frame_pointer = 0
      if frame_pointer:
        break
    if not frame_pointer:
      return base_name

    ptr_size = _ptr_size()
    bridge = _get_bridge(ptr_size)
    hints = None
    try:
      hints = bridge.resolve_heap_hints(_GdbHintsResolver())
    except Exception:
      if _VERBOSE:
        traceback.print_exc()
      hints = None
    suffix = bridge.frame_suffix(frame_pointer, _read_memory_callback, hints)
    if not suffix:
      return base_name
    if not base_name:
      return suffix.strip()
    return f"{base_name}{suffix}"


class V8DbgFrameFilter:
  """Registers the V8 frame decorator."""

  def __init__(self):
    self.name = "v8dbg_bridge"
    self.priority = 100
    self.enabled = True
    progspace = gdb.current_progspace()
    if progspace is not None:
      progspace.frame_filters[self.name] = self
    else:
      gdb.frame_filters[self.name] = self

  def filter(self, iterator):
    """Wrap each frame with the V8-aware decorator."""
    return (V8DbgFrameDecorator(frame_obj) for frame_obj in iterator)


class V8Command(gdb.Command):
  """`v8 <subcommand> ...` dispatcher for V8 debug-helper commands.

  Currently implements `v8 inspect <addr>`. Use `v8 help` for the full list.
  """

  def __init__(self):
    super().__init__("v8", gdb.COMMAND_USER, prefix=False)

  def invoke(self, argument, _from_tty):
    """Dispatch the command and stream output back to the gdb console."""
    try:
      argv = gdb.string_to_argv(argument)
    except Exception:
      argv = argument.split()
    ptr_size = _ptr_size()
    bridge = _get_bridge(ptr_size)
    buffer = io.StringIO()
    try:
      bridge.dispatch_v8_command(
          argv,
          buffer,
          read_memory=_read_memory_callback,
          eval_address=_evaluate_address_in_gdb,
          hints_resolver=_GdbHintsResolver(),
      )
    except Exception:
      if _VERBOSE:
        traceback.print_exc()
      gdb.write("v8: command failed; rerun with V8_DEBUG_HELPER_VERBOSE=1\n",
                gdb.STDERR)
      return
    text = buffer.getvalue()
    if text:
      gdb.write(text)
      if not text.endswith("\n"):
        gdb.write("\n")


V8DbgFrameFilter()
V8Command()
