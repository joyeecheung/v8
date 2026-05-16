# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Shared ctypes bridge for the v8_debug_helper C ABI.

This module loads libv8_debug_helper and exposes the surfaces used by the
GDB and LLDB plugins: frame annotation, object inspection (`v8 inspect`),
heap-hint discovery (locating the metadata pointer table and the
Heap::isolate_ field offset), and a small dispatch helper for the `v8`
debugger command.
"""

import argparse
import ctypes
import dataclasses
import os
import re
import types
from typing import List

_MEMORY_ACCESS_OK = 0
_MEMORY_ACCESS_INVALID = 1

_STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"')

_FRAME_BRIEFS_ENABLED = os.environ.get("V8_DEBUG_HELPER_FRAME_BRIEFS", "1") != "0"

# PropertyKind values from
# tools/debug_helper/debug-helper.h.
PROPERTY_KIND_SINGLE = 0
PROPERTY_KIND_ARRAY_OF_KNOWN_SIZE = 1
PROPERTY_KIND_ARRAY_OF_UNKNOWN_SIZE_INVALID = 2
PROPERTY_KIND_ARRAY_OF_UNKNOWN_SIZE_INACCESSIBLE = 3

# TypeCheckResult values from
# tools/debug_helper/debug-helper.h.
TYPE_CHECK_SMI = 0
TYPE_CHECK_WEAK_REF = 1
TYPE_CHECK_USED_MAP = 2
TYPE_CHECK_KNOWN_MAP_POINTER = 3
TYPE_CHECK_USED_TYPE_HINT = 4
TYPE_CHECK_UNABLE_TO_DECOMPRESS = 5
TYPE_CHECK_OBJECT_POINTER_INVALID = 6
TYPE_CHECK_OBJECT_POINTER_INACCESSIBLE = 7
TYPE_CHECK_MAP_POINTER_INVALID = 8
TYPE_CHECK_MAP_POINTER_INACCESSIBLE = 9
TYPE_CHECK_UNKNOWN_INSTANCE_TYPE = 10
TYPE_CHECK_UNKNOWN_TYPE_HINT = 11

_TYPE_CHECK_LABELS = {
    TYPE_CHECK_USED_TYPE_HINT: "via type hint",
    TYPE_CHECK_UNABLE_TO_DECOMPRESS: "unable to decompress",
    TYPE_CHECK_OBJECT_POINTER_INVALID: "object pointer invalid",
    TYPE_CHECK_OBJECT_POINTER_INACCESSIBLE: "Object inaccessible",
    TYPE_CHECK_MAP_POINTER_INVALID: "Map pointer invalid",
    TYPE_CHECK_MAP_POINTER_INACCESSIBLE: "Map inaccessible",
    TYPE_CHECK_UNKNOWN_INSTANCE_TYPE: "unknown instance type",
    TYPE_CHECK_UNKNOWN_TYPE_HINT: "unknown type hint",
}


@dataclasses.dataclass
class StructFieldSummary:
  """Decoupled snapshot of a Torque-struct field from a property."""
  name: str
  type: str
  offset: int
  num_bits: int
  shift_bits: int


@dataclasses.dataclass
class PropertySummary:
  """Decoupled snapshot of one property; safe to outlive the C result."""
  name: str
  type: str
  address: int
  kind: int
  size: int
  num_values: int
  struct_fields: List[StructFieldSummary]
  is_tagged: bool


@dataclasses.dataclass
class InspectResult:
  """Decoupled snapshot of GetObjectProperties output."""
  brief: str
  type: str
  type_check_result: int
  properties: List[PropertySummary]
  guessed_types: List[str]
  address: int  # The original tagged value the caller asked about.


@dataclasses.dataclass
class HeapHints:
  """Python mirror of HeapAddresses; converted to the C struct by inspect()."""
  map_space_first_page: int = 0
  old_space_first_page: int = 0
  read_only_space_first_page: int = 0
  any_heap_pointer: int = 0
  metadata_pointer_table: int = 0
  isolate_heap_member_offset: int = 0

  def with_any_heap_pointer(self, addr):
    """Return a copy that sets `any_heap_pointer` if not already set."""
    if self.any_heap_pointer:
      return self
    return dataclasses.replace(self, any_heap_pointer=addr)


class StructProperty(ctypes.Structure):
  _fields_ = [
      ("name", ctypes.c_char_p),
      ("type", ctypes.c_char_p),
      ("offset", ctypes.c_size_t),
      ("num_bits", ctypes.c_uint8),
      ("shift_bits", ctypes.c_uint8),
  ]


StructPropertyPointer = ctypes.POINTER(StructProperty)


def _make_types(ptr_size):
  """Create ctypes types parameterized by the target pointer size (4 or 8)."""
  c_uintptr = ctypes.c_uint64 if ptr_size == 8 else ctypes.c_uint32
  uintptr_max = (1 << (ptr_size * 8)) - 1

  class ObjectProperty(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("type", ctypes.c_char_p),
        ("address", c_uintptr),
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
        ("map_space_first_page", c_uintptr),
        ("old_space_first_page", c_uintptr),
        ("read_only_space_first_page", c_uintptr),
        ("any_heap_pointer", c_uintptr),
        ("metadata_pointer_table", c_uintptr),
        ("isolate_heap_member_offset", c_uintptr),
    ]

  MemoryAccessor = ctypes.CFUNCTYPE(ctypes.c_int, c_uintptr, ctypes.c_void_p,
                                    ctypes.c_size_t)

  return types.SimpleNamespace(
      c_uintptr=c_uintptr,
      uintptr_max=uintptr_max,
      ObjectProperty=ObjectProperty,
      ObjectPropertyPointer=ObjectPropertyPointer,
      ObjectPropertiesResult=ObjectPropertiesResult,
      StackFrameResult=StackFrameResult,
      HeapAddresses=HeapAddresses,
      MemoryAccessor=MemoryAccessor,
  )


def _is_tagged_type(type_name):
  """Heuristic: a tagged type starts with v8::internal::Tagged< or is Object."""
  if not type_name:
    return False
  return ("Tagged<" in type_name or "v8::internal::Object" in type_name or
          "v8::internal::HeapObject" in type_name or
          "v8::internal::Smi" in type_name or "::TaggedMember<" in type_name)


def _is_smi_tagged(value):
  """Return True if a tagged pointer is a Smi (low bit clear)."""
  return (int(value) & 1) == 0


# TODO(joyee): add a method to check that the library is compatible with the binary
# being debugged e.g. the V8 build configs should match.
class DebuggerBridge:

  def __init__(self, library_path=None, ptr_size=None):
    """Set up a lazily loaded bridge for one target pointer width."""
    self._library_path = library_path
    self._library_handle = None
    if ptr_size is None:
      ptr_size = ctypes.sizeof(ctypes.c_void_p)
    self._ptr_size = ptr_size
    self._t = _make_types(ptr_size)
    self._heap_hints_cache = {}  # (resolver_id, isolate_addr) -> HeapHints
    self._frame_brief_cache = {}  # (fp, value) -> brief string

  def _resolved_library_path(self):
    """Resolve the debug-helper shared library from config or environment."""
    lib_path = self._library_path or os.environ.get("V8_DEBUG_HELPER_LIB_PATH")
    if not lib_path:
      raise RuntimeError(
          "Set V8_DEBUG_HELPER_LIB_PATH to the v8_debug_helper shared library")
    return os.path.abspath(lib_path)

  def _library(self):
    """Load and type the C ABI once for this bridge instance."""
    if self._library_handle is None:
      library = ctypes.CDLL(self._resolved_library_path())
      t = self._t
      library._v8_debug_helper_GetStackFrame.argtypes = [
          t.c_uintptr,
          t.MemoryAccessor,
      ]
      library._v8_debug_helper_GetStackFrame.restype = ctypes.POINTER(
          t.StackFrameResult)
      library._v8_debug_helper_Free_StackFrameResult.argtypes = [
          ctypes.POINTER(t.StackFrameResult)
      ]
      library._v8_debug_helper_Free_StackFrameResult.restype = None
      library._v8_debug_helper_GetObjectProperties.argtypes = [
          t.c_uintptr,
          t.MemoryAccessor,
          ctypes.POINTER(t.HeapAddresses),
          ctypes.c_char_p,
      ]
      library._v8_debug_helper_GetObjectProperties.restype = ctypes.POINTER(
          t.ObjectPropertiesResult)
      library._v8_debug_helper_Free_ObjectPropertiesResult.argtypes = [
          ctypes.POINTER(t.ObjectPropertiesResult)
      ]
      library._v8_debug_helper_Free_ObjectPropertiesResult.restype = None
      self._library_handle = library
    return self._library_handle

  def _make_memory_accessor(self, read_memory):
    """Adapt a debugger-specific memory reader to the C callback ABI."""

    def callback(address, destination, byte_count):
      try:
        data = read_memory(address, byte_count)
      except Exception:
        return _MEMORY_ACCESS_INVALID
      if len(data) != byte_count:
        return _MEMORY_ACCESS_INVALID
      ctypes.memmove(destination, data, byte_count)
      return _MEMORY_ACCESS_OK

    return self._t.MemoryAccessor(callback)

  def _hints_to_c(self, hints):
    """Convert a HeapHints dataclass into the C HeapAddresses struct."""
    return self._t.HeapAddresses(
        int(hints.map_space_first_page) & self._t.uintptr_max,
        int(hints.old_space_first_page) & self._t.uintptr_max,
        int(hints.read_only_space_first_page) & self._t.uintptr_max,
        int(hints.any_heap_pointer) & self._t.uintptr_max,
        int(hints.metadata_pointer_table) & self._t.uintptr_max,
        int(hints.isolate_heap_member_offset) & self._t.uintptr_max,
    )

  def _summarize_property(self, c_prop):
    """Copy a C ObjectProperty into a Python PropertySummary."""
    type_name = c_prop.type.decode("utf-8") if c_prop.type else ""
    struct_fields = []
    for i in range(c_prop.num_struct_fields):
      sf = c_prop.struct_fields[i].contents
      struct_fields.append(
          StructFieldSummary(
              name=sf.name.decode("utf-8") if sf.name else "",
              type=sf.type.decode("utf-8") if sf.type else "",
              offset=int(sf.offset),
              num_bits=int(sf.num_bits),
              shift_bits=int(sf.shift_bits),
          ))
    return PropertySummary(
        name=c_prop.name.decode("utf-8") if c_prop.name else "",
        type=type_name,
        address=int(c_prop.address) & self._t.uintptr_max,
        kind=int(c_prop.kind),
        size=int(c_prop.size),
        num_values=int(c_prop.num_values),
        struct_fields=struct_fields,
        is_tagged=_is_tagged_type(type_name),
    )

  def inspect(self, tagged_ptr, heap_hints, read_memory, type_hint=None):
    """Wrap _v8_debug_helper_GetObjectProperties; return an InspectResult.

    Returns None only if the C call itself fails to allocate a result. Any
    partial-data condition (e.g. Map inaccessible) is reported via
    `type_check_result`.
    """
    if heap_hints is None:
      heap_hints = HeapHints()
    memory_callback = self._make_memory_accessor(read_memory)
    c_hints = self._hints_to_c(heap_hints)
    library = self._library()
    type_hint_bytes = (
        type_hint.encode("utf-8") if isinstance(type_hint, str) else type_hint)
    tagged = int(tagged_ptr) & self._t.uintptr_max
    result_ptr = library._v8_debug_helper_GetObjectProperties(
        tagged, memory_callback, ctypes.byref(c_hints), type_hint_bytes)
    if not result_ptr:
      return None
    try:
      result = result_ptr.contents
      brief = result.brief.decode("utf-8",
                                  errors="replace") if result.brief else ""
      type_name = result.type.decode("utf-8") if result.type else ""
      properties = []
      for i in range(result.num_properties):
        properties.append(self._summarize_property(result.properties[i].contents))
      guessed_types = []
      for i in range(result.num_guessed_types):
        g = result.guessed_types[i]
        if g:
          guessed_types.append(g.decode("utf-8", errors="replace"))
      return InspectResult(
          brief=brief,
          type=type_name,
          type_check_result=int(result.type_check_result),
          properties=properties,
          guessed_types=guessed_types,
          address=tagged,
      )
    finally:
      library._v8_debug_helper_Free_ObjectPropertiesResult(result_ptr)

  # ---------------- string-property helpers ----------------

  def _extract_string_from_brief(self, brief):
    """Extract string content from object briefs."""
    if not brief:
      return ""
    match = _STRING_LITERAL_RE.search(brief)
    if match:
      return match.group(0)[1:-1]
    marker = " (0x"
    if marker in brief:
      return brief.rsplit(marker, 1)[0]
    return brief

  def _resolve_property_string(self,
                               props,
                               prop_name,
                               read_memory,
                               allow_brief_fallback=True):
    """Resolve one debug-helper property into a Python string when possible."""
    prop = props.get(prop_name)
    if prop is None or not prop.address or not prop.size:
      return ""

    raw_value = int.from_bytes(
        read_memory(prop.address, prop.size), byteorder="little", signed=False)

    # `any_heap_pointer` is used by the debug helper to locate the V8 cage /
    # read-only space. We pass `prop.address` here, which is the address of
    # the parent object's *field* rather than a heap object pointer, but it
    # still lies within the isolate's heap and is therefore good enough for
    # cage detection.
    hints = HeapHints(any_heap_pointer=int(prop.address) & self._t.uintptr_max)
    result = self.inspect(raw_value, hints, read_memory)
    if result is None:
      return ""
    # TODO(joyee): repeatedly decoding the same string can be expensive,
    # but for live debugging stale caches can be tricky to manage. Find
    # a way to tie the lifetime of these caches correctly with debugger
    # action cycles so that we can speed up repeated reads.
    for p in result.properties:
      if p.name in ("chars", "raw_characters") and p.num_values > 0:
        size_per_char = p.size  # 1 for char, 2 for char16_t
        try:
          data = read_memory(p.address, p.num_values * size_per_char)
          if size_per_char == 1:
            return data.decode("latin-1")
          return data.decode("utf-16-le")
        except Exception:
          break
    if not allow_brief_fallback:
      return ""
    # Fall back to the display-oriented brief only for non-source strings.
    return self._extract_string_from_brief(result.brief)

  def _decode_tagged_smi(self, raw_value, field_width):
    """Decode one tagged Smi value read from target memory."""
    if field_width <= 4:
      return ctypes.c_int32(raw_value).value >> 1
    return ctypes.c_int64(raw_value).value >> 32

  def _position_from_offset(self, script_source, char_offset):
    """Convert a source character offset to a user-facing line and column."""
    if not script_source or not 0 <= char_offset <= len(script_source):
      return None

    # TODO(joyee): we likely want to cache this for repeated lookups within
    # the same script, but for live debugging we need to be careful to
    # invalidate the cache correctly.
    line = script_source.count("\n", 0, char_offset) + 1
    last_newline = script_source.rfind("\n", 0, char_offset)
    column = (
        char_offset + 1 if last_newline == -1 else char_offset - last_newline)
    return (line, column)

  def _decode_position(self, script_source, function_name, offset_prop,
                       read_memory):
    """Decode function_character_offset into a (line, column) pair."""
    if (offset_prop is None or not offset_prop.address or
        not offset_prop.struct_fields):
      return None

    fields = {f.name: f for f in offset_prop.struct_fields}
    start_field = fields.get("start")
    end_field = fields.get("end")
    if start_field is None or end_field is None:
      return None

    # The debug helper reports the total struct size as 2 * kTaggedSize for the
    # target build, so derive the per-field width from that build-specific size.
    if start_field.offset != 0 or offset_prop.size % 2 != 0:
      return None
    field_width = offset_prop.size // 2
    if field_width not in (4, 8):
      return None
    raw_start = int.from_bytes(
        read_memory(offset_prop.address + start_field.offset, field_width),
        byteorder="little",
        signed=False,
    )
    char_offset = self._decode_tagged_smi(raw_start, field_width)
    position = self._position_from_offset(script_source, char_offset)
    if position is not None:
      return position

    # Top-level scripts without source can still be reported as 1:1.
    if not script_source and char_offset == 0 and function_name == "":
      return (1, 1)
    return None

  # ---------------- JS frame description ----------------

  # StandardFrameConstants offsets on x64/arm64 release builds, where
  # V8_EMBEDDED_CONSTANT_POOL_BOOL is false (kCPSlotSize=0). PPC/S390X set
  # kCPSlotSize=kSystemPointerSize and shift every offset; the frame brief
  # helper short-circuits there.
  _MAX_ARGS_RENDERED = 4

  def _argc_offset(self):
    return -3 * self._ptr_size  # kArgCOffset (kCPSlotSize=0)

  def _param0_offset(self):
    return 2 * self._ptr_size  # kCallerSPOffset (kFPOnStackSize+kPCOnStackSize)

  def _read_tagged(self, addr, read_memory):
    """Read one tagged-pointer-sized slot from target memory."""
    try:
      data = read_memory(addr, self._ptr_size)
    except Exception:
      return None
    if len(data) != self._ptr_size:
      return None
    return int.from_bytes(data, byteorder="little", signed=False)

  def _read_js_frame_args(self, frame_pointer, read_memory):
    """Return (receiver, args, user_argc) for one JS frame, or (None, [], 0).

    `args` is the tail of positional arguments capped at _MAX_ARGS_RENDERED.
    `user_argc` is the user-visible argument count (excludes the receiver).
    The raw frame argc field counts the receiver slot too; we subtract it.
    """
    if not frame_pointer:
      return (None, [], 0)
    try:
      argc_bytes = read_memory(frame_pointer + self._argc_offset(),
                               self._ptr_size)
    except Exception:
      return (None, [], 0)
    if len(argc_bytes) != self._ptr_size:
      return (None, [], 0)
    # argc is a raw integer (not a Smi) and counts the receiver slot.
    raw_argc = int.from_bytes(argc_bytes, "little", signed=False) & 0xFFFFFFFF
    user_argc = max(0, int(raw_argc) - 1)
    receiver = self._read_tagged(frame_pointer + self._param0_offset(),
                                 read_memory)
    args = []
    rendered = min(user_argc, self._MAX_ARGS_RENDERED)
    for i in range(rendered):
      args.append(
          self._read_tagged(
              frame_pointer + self._param0_offset() + (i + 1) * self._ptr_size,
              read_memory))
    return (receiver, args, user_argc)

  def _brief_for_value(self, value, read_memory, hints, fp_for_cache=None):
    """Return a short brief like <String: "x"> for one tagged value.

    Always defers Smi decoding to debug-helper because the Smi shift depends
    on the target build's `kTaggedSize` (compressed-pointer builds shift by
    1; uncompressed shift by 32).
    """
    if value is None:
      return "<?>"
    cache_key = (fp_for_cache, int(value)) if fp_for_cache is not None else None
    if cache_key is not None and cache_key in self._frame_brief_cache:
      return self._frame_brief_cache[cache_key]

    use_hints = hints
    if use_hints is None or not use_hints.any_heap_pointer:
      use_hints = (hints or HeapHints()).with_any_heap_pointer(int(value))

    result = self.inspect(value, use_hints, read_memory)
    if result is None:
      brief = "<?>"
    else:
      brief = _short_brief(result)
    if cache_key is not None:
      self._frame_brief_cache[cache_key] = brief
    return brief

  def describe_js_frame(self, frame_pointer, read_memory, hints=None):
    """Return high-level JS frame metadata, or None if the frame is unusable."""
    if not frame_pointer:
      return None

    memory_callback = self._make_memory_accessor(read_memory)
    library = self._library()
    result_ptr = library._v8_debug_helper_GetStackFrame(
        int(frame_pointer) & self._t.uintptr_max, memory_callback)
    if not result_ptr:
      return None
    try:
      result = result_ptr.contents
      props = {}
      # Convert the properties array (PropertySummary list) into a dict.
      for index in range(result.num_properties):
        summary = self._summarize_property(result.properties[index].contents)
        props[summary.name] = summary
      if "currently_executing_jsfunction" not in props:
        return None

      function_name = self._resolve_property_string(props, "function_name",
                                                    read_memory)
      script_name = self._resolve_property_string(props, "script_name",
                                                  read_memory)
      script_source = self._resolve_property_string(
          props, "script_source", read_memory, allow_brief_fallback=False)
      position = self._decode_position(
          script_source,
          function_name,
          props.get("function_character_offset"),
          read_memory,
      )

      if function_name == "" and not script_name:
        return None
      if function_name == "":
        function_name = "<anonymous>"

      receiver, args, total_argc = (None, [], 0)
      receiver_brief = ""
      args_brief = []
      if _FRAME_BRIEFS_ENABLED:
        receiver, args, total_argc = self._read_js_frame_args(
            frame_pointer, read_memory)
        if receiver is not None:
          receiver_brief = self._brief_for_value(receiver, read_memory, hints,
                                                 frame_pointer)
        for value in args:
          args_brief.append(
              self._brief_for_value(value, read_memory, hints, frame_pointer))

      return {
          "function_name": function_name,
          "script_name": script_name,
          "position": position,
          "receiver": receiver,
          "args": args,
          "total_argc": total_argc,
          "receiver_brief": receiver_brief,
          "args_brief": args_brief,
      }
    finally:
      library._v8_debug_helper_Free_StackFrameResult(result_ptr)

  def frame_suffix(self, frame_pointer, read_memory, hints=None):
    """Format one bracket-wrapped JS annotation suffix for a debugger frame.

    With frame briefs enabled (the default), produces:

      [<function>(this=<brief>, <brief>, ...) @ <script>:<line>:<column>]

    Otherwise:

      [<function> @ <script>:<line>:<column>]

    If source text cannot be recovered but the script name still can, the
    annotation degrades to drop the `@ ...` location.
    """
    annotation = self.describe_js_frame(frame_pointer, read_memory, hints)
    if not annotation:
      return ""
    function_name = annotation.get("function_name") or "<anonymous>"
    script_name = annotation.get("script_name")
    position = annotation.get("position")
    location_suffix = ""
    if position:
      location_suffix = f":{position[0]}:{position[1]}"

    call_suffix = ""
    if _FRAME_BRIEFS_ENABLED:
      receiver_brief = annotation.get("receiver_brief") or ""
      args_brief = annotation.get("args_brief") or []
      total_argc = annotation.get("total_argc") or 0
      pieces = []
      if receiver_brief:
        pieces.append(f"this={receiver_brief}")
      pieces.extend(args_brief)
      remaining = total_argc - len(args_brief)
      if remaining > 0:
        pieces.append(f"...({remaining} more)")
      if pieces:
        call_suffix = f"({', '.join(pieces)})"

    if script_name:
      return f" [{function_name}{call_suffix} @ {script_name}{location_suffix}]"
    return f" [{function_name}{call_suffix}]"

  # ---------------- heap-hint resolution ----------------

  def resolve_heap_hints(self, resolver, isolate_addr=None):
    """Walk g_current_isolate_ -> IsolateGroup to populate HeapHints.

    `resolver` is any object implementing:
      - read_pointer(addr) -> int | None
      - global_symbol_address(name) -> int | None
      - field_offset(type_name, field_name) -> int | None

    Returns a HeapHints instance, possibly partial. Cached per
    (resolver, isolate_addr).
    """
    resolver_key = id(resolver)
    cache_key = (resolver_key, isolate_addr)
    if cache_key in self._heap_hints_cache:
      return self._heap_hints_cache[cache_key]

    hints = HeapHints()

    if isolate_addr is None:
      sym_addr = _safe_call(resolver.global_symbol_address,
                            "v8::internal::g_current_isolate_")
      if not sym_addr:
        sym_addr = _safe_call(resolver.global_symbol_address,
                              "_ZN2v88internal18g_current_isolate_E")
      if sym_addr:
        isolate_addr = _safe_call(resolver.read_pointer, sym_addr)

    if isolate_addr:
      group_offset = _safe_call(resolver.field_offset, "v8::internal::Isolate",
                                "isolate_group_")
      if group_offset is not None:
        group_ptr = _safe_call(resolver.read_pointer,
                               isolate_addr + group_offset)
        if group_ptr:
          mpt_offset = _safe_call(resolver.field_offset,
                                  "v8::internal::IsolateGroup",
                                  "metadata_pointer_table_")
          if mpt_offset is not None:
            hints.metadata_pointer_table = (group_ptr + mpt_offset) & (
                (1 << (self._ptr_size * 8)) - 1)
      heap_isolate_offset = _safe_call(resolver.field_offset,
                                       "v8::internal::Heap", "isolate_")
      if heap_isolate_offset is not None:
        hints.isolate_heap_member_offset = int(heap_isolate_offset)
      heap_offset = _safe_call(resolver.field_offset, "v8::internal::Isolate",
                               "heap_")
      if heap_offset is not None:
        # any_heap_pointer can be anywhere inside the heap; the Heap object
        # lives inside the Isolate and is a stable choice.
        hints.any_heap_pointer = isolate_addr + heap_offset

    self._heap_hints_cache[cache_key] = hints
    return hints

  # ---------------- v8 command dispatcher ----------------

  def dispatch_v8_command(self, argv, output, read_memory, eval_address=None,
                          hints_resolver=None):
    """Run one `v8 <subcommand> ...` invocation.

    `argv` is the post-`v8` argument list. `output` is a file-like object
    that receives the rendered text. `read_memory(addr, n)` reads target
    memory. `eval_address(text)` (optional) evaluates a debugger expression
    into an integer for `<addr>` arguments. `hints_resolver` is optional
    and used to populate HeapHints.
    """
    handlers = {
        "inspect": _handle_inspect,
        "help": _handle_help,
    }
    if not argv:
      _handle_help(self, [], output, read_memory, eval_address, hints_resolver)
      return
    subcommand, rest = argv[0], argv[1:]
    handler = handlers.get(subcommand)
    if handler is None:
      output.write(f"v8: unknown subcommand '{subcommand}'\n")
      _handle_help(self, [], output, read_memory, eval_address, hints_resolver)
      return
    try:
      handler(self, rest, output, read_memory, eval_address, hints_resolver)
    except _ArgParseExit:
      # argparse already printed the error / help.
      return


# ---------------- output rendering ----------------


def _short_brief(result):
  """Compact one-line brief for a value inside a parent body."""
  if result is None:
    return "<?>"
  tcr = result.type_check_result
  if tcr == TYPE_CHECK_SMI:
    # debug-helper's brief for a Smi looks like "Smi 42". Re-render compactly.
    return _smi_brief_from_inspect(result)
  type_summary = _type_summary(result)
  if not type_summary:
    return "<HeapObject>"
  return f"<{type_summary}>"


def _smi_brief_from_inspect(result):
  """Build a `<Smi: N>` brief from an InspectResult that describes a Smi.

  debug-helper renders Smi briefs as e.g. "42 (0x2a)".
  """
  brief = result.brief or ""
  m = re.match(r"\s*(-?\d+)", brief)
  if m:
    return f"<Smi: {m.group(1)}>"
  return "<Smi>"


def _type_summary(result):
  """Build the angle-bracket summary contents (without the brackets)."""
  brief = (result.brief or "").strip()
  type_name = result.type or ""
  short_type = _short_type_name(type_name)
  condition = _condition_label(result.type_check_result)

  # Prefer a salient short fact from the brief when we have one.
  short_fact = _extract_short_fact(brief, short_type)
  base = short_type or "HeapObject"
  parts = [base]
  if short_fact:
    parts.append(f": {short_fact}")
  if condition:
    parts.append(f" [{condition}]")
  return "".join(parts)


def _short_type_name(type_name):
  """Drop the `v8::internal::` prefix when present."""
  if not type_name:
    return ""
  short = type_name
  if short.startswith("v8::internal::"):
    short = short[len("v8::internal::"):]
  return short


def _condition_label(tcr):
  return _TYPE_CHECK_LABELS.get(tcr, "")


def _extract_short_fact(brief, short_type):
  """Pull the most useful one-liner from `brief`, if any.

  debug-helper briefs look like (typical cases):
    "0xabc <v8::internal::JSGlobalProxy>"        -- no extra info, drop entirely
    "\"hello\" (0xabc <v8::internal::SeqOneByteString>)"   -- keep the quoted string
    "false (0xabc <v8::internal::Oddball>)"      -- keep the leading description
  """
  if not brief:
    return ""
  # Pull the descriptive prefix before " (0x" if present.
  paren_marker = " (0x"
  if paren_marker in brief:
    prefix = brief.split(paren_marker, 1)[0].strip()
    if prefix:
      return prefix
    return ""
  # Otherwise it's just an "0xADDR <type>" form -- nothing useful beyond the
  # type name itself.
  m = re.search(r"<(.*)>", brief, flags=re.DOTALL)
  if not m:
    return brief.strip()
  inner = m.group(1).strip()
  if inner.startswith("v8::internal::"):
    inner = inner[len("v8::internal::"):]
  if short_type and inner == short_type:
    return ""
  return inner


def format_inspect_result(bridge,
                          result,
                          depth=1,
                          array_length=16,
                          string_length=80,
                          read_memory=None,
                          hints=None,
                          _current_depth=0):
  """Render an InspectResult in the llnode-compatible grammar."""
  if result is None:
    return "<?>"

  body_lines = []
  expanded = depth > _current_depth and result.properties
  short_summary = _type_summary(result)

  head = f"0x{result.address:x}:<{short_summary}"
  if result.type_check_result == TYPE_CHECK_SMI:
    return _smi_brief_from_inspect(result)
  if not expanded:
    return f"{head}>"

  rendered_props = _render_properties(
      bridge,
      result.properties,
      depth=depth,
      array_length=array_length,
      string_length=string_length,
      read_memory=read_memory,
      hints=hints,
      current_depth=_current_depth + 1,
  )
  if not rendered_props:
    return f"{head}>"

  joined = ",\n  ".join(rendered_props)
  output = f"{head} {{\n  {joined}}}>"

  if _current_depth == 0 and result.guessed_types:
    output += "\n\ncould be one of (re-run with --type to drill in):"
    for guessed in result.guessed_types:
      output += f"\n  v8 inspect 0x{result.address:x} --type {guessed}"
  return output


def _render_properties(bridge, properties, depth, array_length, string_length,
                       read_memory, hints, current_depth):
  """Render the body -- one rendered string per property, comma-joined later."""
  rendered = []
  for prop in properties:
    rendered.extend(
        _render_one_property(
            bridge,
            prop,
            depth=depth,
            array_length=array_length,
            string_length=string_length,
            read_memory=read_memory,
            hints=hints,
            current_depth=current_depth,
        ))
  return rendered


def _render_one_property(bridge, prop, depth, array_length, string_length,
                         read_memory, hints, current_depth):
  """Render one PropertySummary as a list of one-or-more lines."""
  kind = prop.kind
  if kind == PROPERTY_KIND_ARRAY_OF_UNKNOWN_SIZE_INVALID:
    return [f".{prop.name}=<{_short_type_name(prop.type) or '?'} "
            f"[length unreadable: invalid memory]>"]
  if kind == PROPERTY_KIND_ARRAY_OF_UNKNOWN_SIZE_INACCESSIBLE:
    return [
        f".{prop.name}=<{_short_type_name(prop.type) or '?'} "
        f"[length unreadable: address valid but inaccessible]>"
    ]
  if prop.struct_fields:
    return [_render_struct_property(bridge, prop, read_memory)]
  if kind == PROPERTY_KIND_ARRAY_OF_KNOWN_SIZE:
    return _render_array_property(
        bridge,
        prop,
        depth=depth,
        array_length=array_length,
        string_length=string_length,
        read_memory=read_memory,
        hints=hints,
        current_depth=current_depth,
    )
  # kSingle.
  return [
      f".{prop.name}=" + _render_property_value(
          bridge,
          prop,
          element_index=None,
          depth=depth,
          array_length=array_length,
          string_length=string_length,
          read_memory=read_memory,
          hints=hints,
          current_depth=current_depth,
      )
  ]


def _render_array_property(bridge, prop, depth, array_length, string_length,
                           read_memory, hints, current_depth):
  """Render a kArrayOfKnownSize property with element-cap and ellipsis."""
  total = prop.num_values
  rendered = []
  cap = min(total, array_length)
  for i in range(cap):
    rendered.append(
        f"[{i}]=" + _render_property_value(
            bridge,
            prop,
            element_index=i,
            depth=depth,
            array_length=array_length,
            string_length=string_length,
            read_memory=read_memory,
            hints=hints,
            current_depth=current_depth,
        ))
  if total > cap:
    rendered.append(
        f"...({total - cap} more -- raise --array-length to expand)")
  return [f".{prop.name}=<{_short_type_name(prop.type)}: length={total}>"] + (
      rendered if rendered else [])


def _render_property_value(bridge, prop, element_index, depth, array_length,
                           string_length, read_memory, hints, current_depth):
  """Render one value slot of a property.

  If element_index is None, this is the kSingle value. Otherwise it is the
  i-th element of a known-size array.
  """
  size = prop.size
  if element_index is None:
    address = prop.address
  else:
    address = prop.address + element_index * size
  if not address or not size:
    return "<?>"
  try:
    data = read_memory(address, size)
  except Exception:
    return "<?>"
  if len(data) != size:
    return "<?>"
  raw_value = int.from_bytes(data, "little", signed=False)

  if prop.is_tagged:
    if _is_smi_tagged(raw_value):
      smi = bridge._decode_tagged_smi(raw_value, size)
      return f"<Smi: {smi}>"
    # Recurse for tagged children up to `depth`.
    child_hints = hints
    if child_hints is None or not child_hints.any_heap_pointer:
      child_hints = (hints or HeapHints()).with_any_heap_pointer(int(address))
    child = bridge.inspect(raw_value, child_hints, read_memory)
    if child is None:
      return f"0x{raw_value:x}:<?>"
    return format_inspect_result(
        bridge,
        child,
        depth=depth,
        array_length=array_length,
        string_length=string_length,
        read_memory=read_memory,
        hints=child_hints,
        _current_depth=current_depth,
    )
  # Non-tagged scalar: render as hex with the type name.
  short_type = _short_type_name(prop.type) or "value"
  width_hex = max(2, size * 2)
  return f"<{short_type}: 0x{raw_value:0{width_hex}x}>"


def _render_struct_property(bridge, prop, read_memory):
  """Render a Torque-struct field group (e.g. packed bitfields)."""
  if not prop.address or not prop.size:
    return f".{prop.name}=<?>"
  try:
    data = read_memory(prop.address, prop.size)
  except Exception:
    return f".{prop.name}=<?>"
  if len(data) != prop.size:
    return f".{prop.name}=<?>"
  raw_value = int.from_bytes(data, "little", signed=False)
  short_type = _short_type_name(prop.type) or "struct"
  width_hex = max(2, prop.size * 2)
  inner_parts = []
  for field in prop.struct_fields:
    if field.num_bits:
      mask = (1 << field.num_bits) - 1
      value = (raw_value >> field.shift_bits) & mask
      inner_parts.append(
          f".{field.name}=<Smi: {value}> "
          f"(bits={field.shift_bits}+{field.num_bits})")
    else:
      # Read the sub-field at field.offset within the struct.
      sub_size = max(1, prop.size - field.offset)
      try:
        sub = read_memory(prop.address + field.offset, sub_size)
        value = int.from_bytes(sub, "little", signed=False)
        sub_width = max(2, sub_size * 2)
        inner_parts.append(
            f".{field.name}=<{_short_type_name(field.type) or 'value'}: "
            f"0x{value:0{sub_width}x}>")
      except Exception:
        inner_parts.append(f".{field.name}=<?>")
  inner = ",\n    ".join(inner_parts)
  return (f".{prop.name}=<{short_type}: 0x{raw_value:0{width_hex}x} {{\n    "
          f"{inner}}}>")


# ---------------- argparse-driven subcommand handlers ----------------


class _ArgParseExit(Exception):
  pass


class _SubcommandParser(argparse.ArgumentParser):
  """argparse subclass that writes errors to a caller-supplied stream and
  signals exit via _ArgParseExit instead of calling sys.exit()."""

  def __init__(self, output, *args, **kwargs):
    self._output = output
    super().__init__(*args, **kwargs)

  def _print_message(self, message, _file=None):
    if message:
      self._output.write(message)

  def exit(self, status=0, message=None):
    if message:
      self._output.write(message)
    raise _ArgParseExit()

  def error(self, message):
    self._output.write(f"{self.prog}: error: {message}\n")
    raise _ArgParseExit()


def _parse_address(text, eval_address):
  """Parse `<addr>` text from the CLI; fall back to debugger eval."""
  if text is None:
    return None
  s = text.strip()
  if not s:
    return None
  try:
    if s.lower().startswith("0x"):
      return int(s, 16)
    return int(s, 10)
  except ValueError:
    pass
  if eval_address is not None:
    try:
      result = eval_address(s)
      if result is not None:
        return int(result)
    except Exception:
      return None
  return None


def _handle_inspect(bridge, argv, output, read_memory, eval_address,
                    hints_resolver):
  """`v8 inspect <addr> [--type ...] [--depth N] ...`"""
  parser = _SubcommandParser(
      output,
      prog="v8 inspect",
      description="Inspect a tagged V8 object at <addr>.")
  parser.add_argument("addr", help="Hex/decimal address or debugger expression")
  parser.add_argument("--type", dest="type_hint", default=None,
                      help="Fully-qualified type hint when the Map is unreadable")
  parser.add_argument("--depth", type=int, default=1,
                      help="Recursion depth for inlined children (default 1)")
  parser.add_argument(
      "-l", "--array-length", dest="array_length", type=int, default=16,
      help="Per-array element cap (default 16)")
  parser.add_argument("--string-length", type=int, default=80,
                      help="String truncation length (default 80)")
  args = parser.parse_args(argv)

  address = _parse_address(args.addr, eval_address)
  if address is None:
    output.write(f"v8 inspect: cannot parse address '{args.addr}'\n")
    return

  hints = HeapHints()
  if hints_resolver is not None:
    try:
      hints = bridge.resolve_heap_hints(hints_resolver)
    except Exception:
      hints = HeapHints()
  if not hints.any_heap_pointer:
    # Fall back to passing the target address itself as a hint; this is good
    # enough for cage detection on compressed-pointer builds.
    hints = hints.with_any_heap_pointer(address)

  result = bridge.inspect(address, hints, read_memory, type_hint=args.type_hint)
  if result is None:
    output.write(f"v8 inspect: no result for 0x{address:x}\n")
    return
  output.write(
      format_inspect_result(
          bridge,
          result,
          depth=args.depth,
          array_length=args.array_length,
          string_length=args.string_length,
          read_memory=read_memory,
          hints=hints,
      ))
  output.write("\n")


def _handle_help(bridge, argv, output, read_memory, eval_address,
                 hints_resolver):
  """`v8 help` -- print available subcommands."""
  output.write("v8 -- debug-helper subcommands:\n")
  output.write("  v8 inspect <addr> [--type T] [--depth N] [--array-length N] "
               "[--string-length N]\n")
  output.write("       Inspect a tagged V8 object at <addr>.\n")
  output.write("  v8 help\n")
  output.write("       Show this message.\n")


def _safe_call(fn, *args, **kwargs):
  """Call fn and swallow exceptions; useful for optional debugger lookups."""
  if fn is None:
    return None
  try:
    return fn(*args, **kwargs)
  except Exception:
    return None
