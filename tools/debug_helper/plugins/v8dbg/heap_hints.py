# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""HeapHints and the resolver that populates them from V8 symbols/offsets."""

import dataclasses


@dataclasses.dataclass
class HeapHints:
  """Python mirror of the C HeapAddresses struct."""
  map_space_first_page: int = 0
  old_space_first_page: int = 0
  read_only_space_first_page: int = 0
  any_heap_pointer: int = 0
  metadata_pointer_table: int = 0
  isolate_heap_member_offset: int = 0


def resolve_heap_hints(resolver):
  """Walk V8 symbols/offsets through `resolver` to populate HeapHints.

  `resolver` provides `read_pointer`, `global_symbol_address`, and
  `field_offset` (each returns None on failure). Returned hints may be
  partial; callers wrap in try/except for resolver-level errors.
  """
  hints = HeapHints()
  sym_addr = resolver.global_symbol_address("v8::internal::g_current_isolate_")
  isolate_addr = resolver.read_pointer(sym_addr) if sym_addr else None
  if not isolate_addr:
    return hints

  # metadata_pointer_table: required on compressed-pointer / sandbox builds
  # to resolve tagged pointers through MemoryChunk metadata.
  group_offset = resolver.field_offset("v8::internal::Isolate",
                                       "isolate_group_")
  if group_offset is not None:
    group_ptr = resolver.read_pointer(isolate_addr + group_offset)
    mpt_offset = resolver.field_offset("v8::internal::IsolateGroup",
                                       "metadata_pointer_table_")
    if group_ptr and mpt_offset is not None:
      hints.metadata_pointer_table = group_ptr + mpt_offset

  # isolate_heap_member_offset: lets debug-helper walk Heap back to Isolate
  # without depending on the debugger and target builds sharing a layout.
  heap_isolate_offset = resolver.field_offset("v8::internal::Heap", "isolate_")
  if heap_isolate_offset is not None:
    hints.isolate_heap_member_offset = int(heap_isolate_offset)

  # any_heap_pointer: a stable address inside the isolate's heap, used by
  # debug-helper for cage detection on compressed-pointer builds.
  heap_offset = resolver.field_offset("v8::internal::Isolate", "heap_")
  if heap_offset is not None:
    hints.any_heap_pointer = isolate_addr + heap_offset

  return hints
