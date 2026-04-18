# V8 Debugger Bridge Demo

This directory contains Python debugger glue that loads the real
`libv8_debug_helper.so` and uses `_v8_debug_helper_GetStackFrame()` to append
JavaScript frame information to GDB and LLDB backtraces.

For an architecture-focused explanation of the idea behind the prototype, see
`DESIGN.md`.

## Files

- `debugger_bridge.py`: Shared `ctypes` bridge for the exported
  `v8_debug_helper` C ABI.
- `gdb_adapter.py`: GDB frame filter and frame decorator.
- `lldb_adapter.py`: LLDB `frame-format` callback.
- `test_script.js`: Small JavaScript file that triggers `JsonStringify`.
- `run_demo.py`: Small Python smoke test for library-path resolution and brief
  string normalization.

## Prerequisites

This bridge expects a V8 build that already contains:

```sh
out.gn/x64.release/d8
out.gn/x64.release/libv8_debug_helper.so
```

The default scripts look in `out.gn/x64.release`, and you can override the
library path with `V8_DEBUG_HELPER_LIB_PATH`.

## Python Smoke Test

From this directory:

```sh
make python-test
```

Expected output includes the resolved debug-helper library path and a normalized
string brief.

## Run In GDB

From this directory:

```sh
make gdb-test
```

Equivalent manual command:

```sh
V8_DEBUG_HELPER_LIB_PATH="$PWD/../../out.gn/x64.release/libv8_debug_helper.so" \
gdb -nx -q -batch \
  -iex 'set debuginfod enabled off' \
  -iex 'source ../gdbinit' \
  -iex 'source gdb_adapter.py' \
  -ex 'file ../../out.gn/x64.release/d8' \
  -ex 'break v8::internal::JsonStringify' \
  -ex 'run ./test_script.js' \
  -ex 'bt'
```

Expected output includes JS annotations appended to V8 builtin frames, for
example:

```text
#1  v8::internal::Builtin_JsonStringify(...) [js <anonymous>]
#3  Builtins_InterpreterEntryTrampoline [js a @ .../test_script.js]
#4  Builtins_InterpreterEntryTrampoline [js b @ .../test_script.js]
```

## Run In LLDB

From this directory:

```sh
make lldb-test
```

Equivalent manual command:

```sh
V8_DEBUG_HELPER_LIB_PATH="$PWD/../../out.gn/x64.release/libv8_debug_helper.so" \
lldb -b \
  -O 'command script import lldb_adapter.py' \
  -O 'target create ../../out.gn/x64.release/d8' \
  -O 'breakpoint set --name v8::internal::JsonStringify' \
  -O 'settings set target.run-args ./test_script.js' \
  -O 'run' \
  -O 'bt'
```

Expected output includes:

```text
(lldb) command script import lldb_adapter.py
Loaded v8dbg frame formatter from .../out.gn/x64.release/libv8_debug_helper.so
frame #3: ... Builtins_InterpreterEntryTrampoline + ... [js a @ .../test_script.js]
frame #4: ... Builtins_InterpreterEntryTrampoline + ... [js b @ .../test_script.js]
```

## Notes

- `debugger_bridge.py` calls `_v8_debug_helper_GetStackFrame()` for each V8
  builtin frame and resolves the `function_name` / `script_name` properties via
  `_v8_debug_helper_GetObjectProperties()`.
- Decoration is intentionally restricted to frames whose symbol name contains
  `Builtin`, to avoid smearing JS metadata across unrelated C++ frames.
- The GDB test path sources [tools/gdbinit](tools/gdbinit) so V8's custom
  unwinder is active before the frame decorator runs.
- `V8_DEBUG_HELPER_LIB_PATH` can be set to override the shared-library path for
  Python, GDB, and LLDB.
- `make test` runs the Python, GDB, and LLDB checks in sequence.