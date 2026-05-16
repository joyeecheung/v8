# Copyright 2026 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Parser and dispatcher for the `v8` debugger command."""

import dataclasses

from .heap_hints import HeapHints, resolve_heap_hints
from .inspect import format_inspect_result

_V8_USAGE = (
    "usage: v8 inspect <addr> [--type T] [--depth N] [-l|--array-length N]\n")


def dispatch_v8_command(bridge, argv, output, read_memory, eval_address=None,
                        hints_resolver=None):
  """Run one `v8 <subcommand> ...` invocation."""
  if not argv or argv[0] != "inspect":
    output.write(_V8_USAGE)
    return
  _run_inspect(bridge, argv[1:], output, read_memory, eval_address,
               hints_resolver)


def _parse_address(text, eval_address):
  """Parse `<addr>` text from the CLI; fall back to debugger eval."""
  s = (text or "").strip()
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


def _run_inspect(bridge, argv, output, read_memory, eval_address,
                 hints_resolver):
  """`v8 inspect <addr> [--type T] [--depth N] [-l|--array-length N]`.

  Unknown flags and extra positionals print an error and return. Bad or
  missing values for --depth/--array-length/--type raise to the caller.
  """
  type_hint = None
  depth = 1
  array_length = 16
  addr_text = None
  it = iter(argv)
  for token in it:
    if token == "--type":
      type_hint = next(it)
    elif token == "--depth":
      depth = int(next(it))
    elif token in ("-l", "--array-length"):
      array_length = int(next(it))
    elif token.startswith("-"):
      output.write(f"v8 inspect: unknown flag '{token}'\n")
      return
    elif addr_text is None:
      addr_text = token
    else:
      output.write(f"v8 inspect: extra positional arg '{token}'\n")
      return

  address = _parse_address(addr_text, eval_address)
  if address is None:
    output.write(_V8_USAGE)
    return

  hints = HeapHints()
  if hints_resolver is not None:
    hints = resolve_heap_hints(hints_resolver)
  if not hints.any_heap_pointer:
    hints = dataclasses.replace(hints, any_heap_pointer=address)

  result = bridge.inspect(address, hints, read_memory, type_hint=type_hint)
  if result is None:
    output.write(f"v8 inspect: no result for 0x{address:x}\n")
    return
  output.write(format_inspect_result(bridge, result, depth=depth,
                                     array_length=array_length,
                                     read_memory=read_memory, hints=hints))
  output.write("\n")
