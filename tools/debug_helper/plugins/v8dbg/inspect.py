# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Data model, conversion, and renderers for `v8 inspect`."""

import ctypes
import dataclasses
import re
from typing import List


# Enum values from tools/debug_helper/debug-helper.h.
PROPERTY_KIND_ARRAY_OF_KNOWN_SIZE = 1
PROPERTY_KIND_ARRAY_OF_UNKNOWN_SIZE_INVALID = 2
PROPERTY_KIND_ARRAY_OF_UNKNOWN_SIZE_INACCESSIBLE = 3
TYPE_CHECK_SMI = 0

# TODO(joyee): surface this through the C ABI instead of re-parsing the brief.
_BRIEF_ADDRESS_RE = re.compile(r"0x([0-9a-fA-F]+)\s+<")


def extract_brief_address(brief):
  """Return the address parsed from a debug-helper brief, or None."""
  if not brief:
    return None
  match = _BRIEF_ADDRESS_RE.search(brief)
  if not match:
    return None
  try:
    return int(match.group(1), 16)
  except ValueError:
    return None


@dataclasses.dataclass
class StructFieldSummary:
  """Torque-struct field within a property."""
  name: str
  type: str
  offset: int
  num_bits: int
  shift_bits: int


@dataclasses.dataclass
class PropertySummary:
  """One property of an inspected object."""
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
  """Python snapshot of GetObjectProperties output; outlives the C result."""
  brief: str
  type: str
  type_check_result: int
  properties: List[PropertySummary]
  guessed_types: List[str]
  address: int
  # Decompressed address parsed from `brief`. Zero if the brief has none.
  display_address: int = 0


def is_smi_tagged(value):
  """True if a tagged pointer is a Smi (low bit clear)."""
  return (int(value) & 1) == 0


def decode_tagged_smi(raw_value, field_width):
  """Decode a tagged Smi. Compressed/32-bit shifts by 1; uncompressed 64-bit by 32."""
  if field_width <= 4:
    return ctypes.c_int32(raw_value).value >> 1
  return ctypes.c_int64(raw_value).value >> 32


def _is_tagged_type(type_name):
  """True if `type_name` is one of V8's tagged wrappers."""
  if not type_name:
    return False
  return ("Tagged<" in type_name or "v8::internal::Object" in type_name or
          "v8::internal::HeapObject" in type_name or
          "v8::internal::Smi" in type_name or "::TaggedMember<" in type_name)


def read_frame_breadcrumb(frame_pointer, ptr_size, read_memory):
  """Return (receiver_address, user_argc) for one JS frame, or (None, None)
  if the slots are unreadable. user_argc excludes the receiver slot.

  Offsets: receiver at fp+2*ptr_size, raw argc at fp-3*ptr_size. Valid for
  kCPSlotSize=0 builds (x64, arm64); PPC/S390X shift every offset. argc
  lives in the low 32 bits of the slot - hence the mask.
  """
  try:
    receiver_bytes = read_memory(frame_pointer + 2 * ptr_size, ptr_size)
    argc_bytes = read_memory(frame_pointer - 3 * ptr_size, ptr_size)
  except Exception:
    return (None, None)
  if len(receiver_bytes) != ptr_size or len(argc_bytes) != ptr_size:
    return (None, None)
  receiver = int.from_bytes(receiver_bytes, "little", signed=False)
  raw_argc = int.from_bytes(argc_bytes, "little", signed=False) & 0xFFFFFFFF
  return (receiver, max(0, raw_argc - 1))


def summarize_property(c_prop, uintptr_max):
  """Copy a C ObjectProperty into a Python PropertySummary."""
  type_name = c_prop.type.decode("utf-8") if c_prop.type else ""
  struct_fields = []
  for i in range(c_prop.num_struct_fields):
    field_ptr = c_prop.struct_fields[i]
    if not field_ptr:
      continue
    try:
      sf = field_ptr.contents
    except Exception:
      continue
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
      address=int(c_prop.address) & uintptr_max,
      kind=int(c_prop.kind),
      size=int(c_prop.size),
      num_values=int(c_prop.num_values),
      struct_fields=struct_fields,
      is_tagged=_is_tagged_type(type_name),
  )


def _compact_brief(result):
  """Compact `<Type[: value]>` brief for one tagged value."""
  type_short = (result.type or "").removeprefix("v8::internal::") or "HeapObject"
  if result.type_check_result == TYPE_CHECK_SMI:
    m = re.match(r"\s*(-?\d+)", result.brief or "")
    return f"<Smi: {m.group(1)}>" if m else "<Smi>"
  brief = (result.brief or "").strip()
  # debug-helper formats `result.brief` as either `<value> (0x<addr> <type>)`
  # or `0x<addr> <type>`. Pull out the descriptive prefix when present.
  paren = brief.find(" (0x")
  if paren > 0:
    return f"<{type_short}: {brief[:paren]}>"
  return f"<{type_short}>"


def format_inspect_result(bridge, result, depth=1, array_length=16,
                          read_memory=None, hints=None, _current_depth=0):
  """Render an InspectResult: head + indented properties, recursing up to `depth`."""
  if result is None:
    return "<?>"
  if result.type_check_result == TYPE_CHECK_SMI:
    return _compact_brief(result)

  display = result.display_address or result.address
  head = f"0x{display:x} {_compact_brief(result)}"
  if _current_depth >= depth or not result.properties:
    return head

  indent = "  " * (_current_depth + 1)
  lines = [head]
  for prop in result.properties:
    for line in _format_property(bridge, prop, depth, array_length, read_memory,
                                 hints, _current_depth + 1):
      lines.append(indent + line)
  if _current_depth == 0 and result.guessed_types:
    lines.append("")
    lines.append("could be one of (re-run with --type to drill in):")
    for guessed in result.guessed_types:
      lines.append(f"  v8 inspect 0x{display:x} --type {guessed}")
  return "\n".join(lines)


def _format_property(bridge, prop, depth, array_length, read_memory, hints,
                     current_depth):
  """Return rendered lines for one property, without leading indent."""
  kind = prop.kind
  if kind == PROPERTY_KIND_ARRAY_OF_UNKNOWN_SIZE_INVALID:
    return [f".{prop.name}=0x{prop.address:x} <length unreadable: invalid memory>"]
  if kind == PROPERTY_KIND_ARRAY_OF_UNKNOWN_SIZE_INACCESSIBLE:
    return [f".{prop.name}=0x{prop.address:x} "
            f"<length unreadable: address valid but inaccessible>"]
  if prop.struct_fields:
    return [_format_struct(prop, read_memory)]
  if kind == PROPERTY_KIND_ARRAY_OF_KNOWN_SIZE:
    return _format_array(bridge, prop, depth, array_length, read_memory, hints,
                         current_depth)
  return [
      f".{prop.name}=" + _format_value(bridge, prop, None, depth, array_length,
                                       read_memory, hints, current_depth)
  ]


def _format_array(bridge, prop, depth, array_length, read_memory, hints,
                  current_depth):
  """Header line plus per-element lines for a kArrayOfKnownSize property."""
  total = prop.num_values
  cap = min(total, array_length)
  type_short = (prop.type or "").removeprefix("v8::internal::") or "?"
  lines = [f".{prop.name}=<{type_short}: length={total}>"]
  for i in range(cap):
    rendered = _format_value(bridge, prop, i, depth, array_length, read_memory,
                             hints, current_depth)
    value_lines = rendered.split("\n")
    lines.append(f"  [{i}]={value_lines[0]}")
    for cont in value_lines[1:]:
      lines.append("    " + cont)
  if total > cap:
    lines.append(f"  ...({total - cap} more)")
  return lines


def _format_value(bridge, prop, element_index, depth, array_length, read_memory,
                  hints, current_depth):
  """Render one value slot; recurses into tagged children up to `depth`."""
  size = prop.size
  address = prop.address if element_index is None else (
      prop.address + element_index * size)
  if not address or not size:
    return "<?>"
  try:
    data = read_memory(address, size)
  except Exception:
    return "<?>"
  if len(data) != size:
    return "<?>"
  raw = int.from_bytes(data, "little", signed=False)

  if prop.is_tagged:
    if is_smi_tagged(raw):
      return f"<Smi: {decode_tagged_smi(raw, size)}>"
    # Reuse the parent's heap hints: any_heap_pointer from any object in
    # the isolate suffices for cage detection, and the other fields
    # (metadata_pointer_table, isolate_heap_member_offset, etc.) are
    # process-wide constants.
    child = bridge.inspect(raw, hints, read_memory)
    if child is None:
      return f"0x{raw:x} <?>"
    return format_inspect_result(bridge, child, depth=depth,
                                 array_length=array_length,
                                 read_memory=read_memory, hints=hints,
                                 _current_depth=current_depth)
  return f"0x{raw:0{max(2, size * 2)}x}"


def _format_struct(prop, read_memory):
  """Render a Torque-struct field group as raw hex.

  TODO(joyee): decode packed bitfields and sub-fields inline (e.g. Map::bit_field).
  """
  if not prop.address or not prop.size:
    return f".{prop.name}=<?>"
  try:
    data = read_memory(prop.address, prop.size)
  except Exception:
    return f".{prop.name}=<?>"
  if len(data) != prop.size:
    return f".{prop.name}=<?>"
  raw = int.from_bytes(data, "little", signed=False)
  return f".{prop.name}=0x{raw:0{prop.size * 2}x}"
