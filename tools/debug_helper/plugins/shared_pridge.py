# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Shared ctypes bridge for the v8_debug_helper C ABI.

This module loads libv8_debug_helper and exposes frame annotation
helpers used by the GDB and LLDB plugins.
"""

import ast
import ctypes
import os
import re


_MEMORY_ACCESS_OK = 0
_MEMORY_ACCESS_INVALID = 1

_STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


class StructProperty(ctypes.Structure):
  _fields_ = [
    ("name", ctypes.c_char_p),
    ("type", ctypes.c_char_p),
    ("offset", ctypes.c_size_t),
    ("num_bits", ctypes.c_uint8),
    ("shift_bits", ctypes.c_uint8),
  ]


StructPropertyPointer = ctypes.POINTER(StructProperty)


class ObjectProperty(ctypes.Structure):
  _fields_ = [
    ("name", ctypes.c_char_p),
    ("type", ctypes.c_char_p),
    ("address", ctypes.c_uint64),
    ("num_values", ctypes.c_size_t),
    ("size", ctypes.c_size_t),
    ("num_struct_fields", ctypes.c_size_t),
    ("struct_fields", ctypes.POINTER(StructPropertyPointer)),
    ("kind", ctypes.c_int),
  ]


ObjectPropertyPointer = ctypes.POINTER(ObjectProperty)


class ObjectPropertiesResult(ctypes.Structure):
  _fields_ = [
    ("type_check_result", ctypes.c_int),
    ("brief", ctypes.c_char_p),
    ("type", ctypes.c_char_p),
    ("num_properties", ctypes.c_size_t),
    ("properties", ctypes.POINTER(ObjectPropertyPointer)),
    ("num_guessed_types", ctypes.c_size_t),
    ("guessed_types", ctypes.POINTER(ctypes.c_char_p)),
  ]


class StackFrameResult(ctypes.Structure):
  _fields_ = [
    ("num_properties", ctypes.c_size_t),
    ("properties", ctypes.POINTER(ObjectPropertyPointer)),
  ]


class HeapAddresses(ctypes.Structure):
  _fields_ = [
    ("map_space_first_page", ctypes.c_uint64),
    ("old_space_first_page", ctypes.c_uint64),
    ("read_only_space_first_page", ctypes.c_uint64),
    ("any_heap_pointer", ctypes.c_uint64),
    ("metadata_pointer_table", ctypes.c_uint64),
    ("isolate_heap_member_offset", ctypes.c_uint64),
  ]


MemoryAccessor = ctypes.CFUNCTYPE(
  ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t
)


class DebuggerBridge:
  def __init__(self, library_path=None):
    self._library_path = library_path
    self._library_handle = None
    # Prevent the ctypes callback from being garbage-collected while the FFI
    # call is in flight by storing a reference on the bridge instance.
    self._memory_callback = None

  def _resolved_library_path(self):
    lib_path = self._library_path or os.environ.get("V8_DEBUG_HELPER_LIB_PATH")
    if not lib_path:
      raise RuntimeError(
          "Set V8_DEBUG_HELPER_LIB_PATH to the v8_debug_helper shared library")
    return os.path.abspath(lib_path)

  def _library(self):
    if self._library_handle is None:
      library = ctypes.CDLL(self._resolved_library_path())
      library._v8_debug_helper_GetStackFrame.argtypes = [
        ctypes.c_uint64,
        MemoryAccessor,
      ]
      library._v8_debug_helper_GetStackFrame.restype = ctypes.POINTER(
        StackFrameResult
      )
      library._v8_debug_helper_Free_StackFrameResult.argtypes = [
        ctypes.POINTER(StackFrameResult)
      ]
      library._v8_debug_helper_GetObjectProperties.argtypes = [
        ctypes.c_uint64,
        MemoryAccessor,
        ctypes.POINTER(HeapAddresses),
        ctypes.c_char_p,
      ]
      library._v8_debug_helper_GetObjectProperties.restype = ctypes.POINTER(
        ObjectPropertiesResult
      )
      library._v8_debug_helper_Free_ObjectPropertiesResult.argtypes = [
        ctypes.POINTER(ObjectPropertiesResult)
      ]
      self._library_handle = library
    return self._library_handle

  def _make_memory_accessor(self, read_memory):
    def callback(address, destination, byte_count):
      try:
        data = read_memory(address, byte_count)
      except Exception:
        return _MEMORY_ACCESS_INVALID
      if len(data) != byte_count:
        return _MEMORY_ACCESS_INVALID
      ctypes.memmove(destination, data, byte_count)
      return _MEMORY_ACCESS_OK

    return MemoryAccessor(callback)

  def _summarize_brief(self, brief):
    if not brief:
      return ""
    match = _STRING_LITERAL_RE.search(brief)
    if match:
      try:
        return ast.literal_eval(match.group(0))
      except Exception:
        return match.group(0)[1:-1]
    marker = " (0x"
    if marker in brief:
      return brief.rsplit(marker, 1)[0]
    return brief

  def _resolve_property_string(self, props, prop_name, read_memory):
    prop = props.get(prop_name)
    if prop is None or not prop.address or not prop.size:
      return ""

    raw_value = int.from_bytes(
      read_memory(prop.address, prop.size), byteorder="little", signed=False)
    self._memory_callback = self._make_memory_accessor(read_memory)
    heap_addresses = HeapAddresses(
      0,
      0,
      0,
      int(prop.address) & ((1 << 64) - 1),
      0,
      0,
    )
    library = self._library()
    result_ptr = library._v8_debug_helper_GetObjectProperties(
      int(raw_value) & ((1 << 64) - 1),
      self._memory_callback,
      ctypes.byref(heap_addresses),
      None,
    )
    if not result_ptr:
      return ""
    try:
      result = result_ptr.contents
      brief = ""
      if result.brief:
        brief = result.brief.decode("utf-8", errors="replace")
      return self._summarize_brief(brief)
    finally:
      library._v8_debug_helper_Free_ObjectPropertiesResult(result_ptr)

  def describe_js_frame(self, frame_pointer, read_memory):
    """Return a dict with JS frame metadata, or None."""
    if not frame_pointer:
      return None

    self._memory_callback = self._make_memory_accessor(read_memory)
    library = self._library()
    result_ptr = library._v8_debug_helper_GetStackFrame(
      int(frame_pointer) & ((1 << 64) - 1), self._memory_callback
    )
    if not result_ptr:
      return None
    try:
      result = result_ptr.contents
      props = {}
      for index in range(result.num_properties):
        prop = result.properties[index].contents
        props[prop.name.decode("utf-8")] = prop
      if "currently_executing_jsfunction" not in props:
        return None

      function_name = self._resolve_property_string(
        props, "function_name", read_memory)
      script_name = self._resolve_property_string(
        props, "script_name", read_memory)
      script_source = self._resolve_property_string(
        props, "script_source", read_memory)

      position = None
      offset_prop = props.get("function_character_offset")
      if offset_prop is not None and offset_prop.address and \
          offset_prop.num_struct_fields != 0:
        fields = {}
        for index in range(offset_prop.num_struct_fields):
          field = offset_prop.struct_fields[index].contents
          fields[field.name.decode("utf-8")] = field
        start_field = fields.get("start")
        if start_field is not None:
          field_width = 4
          if "end" in fields:
            field_width = max(1, fields["end"].offset - start_field.offset)
          raw_start = int.from_bytes(
            read_memory(offset_prop.address + start_field.offset, field_width),
            byteorder="little",
            signed=False,
          )
          char_offset = ctypes.c_int32(raw_start).value >> 1
          if script_source and char_offset >= 0:
            offset = min(char_offset, len(script_source))
            line = script_source.count("\n", 0, offset) + 1
            last_newline = script_source.rfind("\n", 0, offset)
            column = offset + 1 if last_newline == -1 else offset - last_newline
            position = (line, column)

      if function_name == "":
        function_name = "<anonymous>"
      return {
        "function_name": function_name,
        "script_name": script_name,
        "position": position,
      }
    finally:
      library._v8_debug_helper_Free_StackFrameResult(result_ptr)

  def frame_suffix(self, frame_pointer, read_memory):
    """Return a bracket-wrapped annotation string for a JS frame, or ''."""
    annotation = self.describe_js_frame(frame_pointer, read_memory)
    if not annotation:
      return ""
    function_name = annotation.get("function_name") or "<anonymous>"
    script_name = annotation.get("script_name")
    position = annotation.get("position")
    location_suffix = ""
    if position:
      location_suffix = f":{position[0]}:{position[1]}"
    if script_name:
      return f" [{function_name} @ {script_name}{location_suffix}]"
    return f" [{function_name}]"