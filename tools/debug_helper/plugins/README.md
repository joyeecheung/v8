# V8 Debug Helper Plugins

This directory contains Python debugger plugins that load
`libv8_debug_helper` to facilitate post-mortem and live debugging of V8
frames and objects in GDB and LLDB.

## How To Build It

Build the shared debug helper library from the repository root:

```sh
autoninja -C out/<config> v8_debug_helper_shared
```

The plugins load the library from the `V8_DEBUG_HELPER_LIB_PATH`
environment variable.

## How To Use It

First set `V8_DEBUG_HELPER_LIB_PATH` environment variable to the built shared
library.

For GDB, run the following commands:

```sh
source tools/gdbinit
source tools/debug_helper/plugins/gdb_plugin.py
```

For LLDB:

```sh
command script import tools/debug_helper/plugins/lldb_plugin.py
```

The LLDB plugin installs its own `frame-format` setting for the session. Import
it in a debugger session where that takeover is acceptable.

### Current features

Once loaded, the plugins append JavaScript annotations to candidate V8 frames
when you print a backtrace via `bt`, and add a `v8 inspect <addr>` command for
walking tagged objects. Both work on release builds and core dumps -- no
debug-symbol requirements beyond what `libv8_debug_helper` itself needs.

#### Frame annotations

The annotation format is:

```
[<function_name> @ <script_name>:<line>:<column>] (this=0xADDR, argc=N)
```

The trailing `(this=..., argc=...)` breadcrumb publishes the receiver
tagged-pointer and user-visible arg count for the JS frame so you can paste
the receiver straight into `v8 inspect`:

```
(gdb) bt
...
#5 0x... in InterpreterEntryTrampoline [test_func_3 @ throw.js:15:21] (this=0x34f49880471, argc=4)
...
(gdb) v8 inspect 0x34f49880471
```

If source text cannot be recovered but the script name still can, the
annotation degrades to drop the `@ ...` location. If the frame's slots are
unreadable (e.g. partial core dump), the trailing breadcrumb is dropped.

For anonymous functions the name is shown as `<anonymous>`. The line and column
point to the start of the function scope in its definition, which is
normally the `(` of the parameter list (or position 1:1 for the top-level
script scope), not where the function is called, which we cannot
reliably recover in the debugger.

#### `v8 inspect <addr>`

Walks the tagged V8 object at `<addr>` and prints its properties as a head
line followed by one indented `.name=value` line per property. Works on
both gdb and lldb:

```
(gdb) v8 inspect 0x34f49880471
0x34f49880471 <JSArray: length=3>
  .map=0x34f49880409 <Map: for JSArray>
  .properties_or_hash=0x34f49880421 <FixedArray: empty>
  .elements=0x34f49880491 <FixedArray: length=3>
  .length=<Smi: 3>
```

Options:

| Flag | Effect |
|---|---|
| `--type <T>` | Type hint when the Map is unreadable (e.g. `v8::internal::JSArray`). |
| `--depth N` | Inline-recursion depth for child references (default 1). |
| `--array-length N` / `-l N` | Per-array element cap (default 16). |

When the object's Map can't be read (partial dump, corrupted memory),
debug-helper's brief still describes the failure, and the renderer adds a
`could be one of ...` footer with ready-to-paste `--type` suggestions.

#### Release- vs. debug-build coverage

| Surface | Release build / core | Debug build / core |
|---|---|---|
| `bt` JS-frame annotations | Yes | Yes |
| `v8 inspect <addr>` | Yes | Yes |
| `job` / `jss` / `jh` (from [tools/gdbinit](../../gdbinit) / [tools/lldb_commands.py](../../lldb_commands.py)) | No -- uses `_v8_internal_Print_*` which is debug-only | Yes |

## How To Test It

Before running the debugger tests, build the test dependencies:

```sh
autoninja -C out/<config> d8 v8_debug_helper_shared corruption_harness
```

There are several types of targets in the Makefile:

- `prepare-cores` generates core files from the test scripts for reuse in
  `run-core-*` and `test-core-*` targets. The files are saved to `CORE_DIR`,
  which defaults to `$(OUT_DIR)/debug_helper.cores/` and is kept out of
  source control.
- `run-live-*` targets run a debugging session on a test script in
  non-interactive mode and print the output. This is useful for debugging
  the plugins themselves.
  - `run-core-*` targets run the same sessions but load from a prepared core
    file instead of a live process.
- `test-live-{gdb,lldb}` and `test-core-{gdb,lldb}` run the full test
  matrix (backtrace, corruption, and inspect) for one debugger against a
  live process or prepared core file respectively.
- `test-live-{backtrace,corruption,inspect}-{gdb,lldb}` and the matching
  `test-core-inspect-*` targets run individual suites.
- `test-live` and `test-core` run the full matrix on both debuggers.

On macOS, with `lldb` installed globally, the output directory is
assumed to be `out/arm64.release`. Build and run the tests with:

```sh
autoninja -C out/arm64.release d8 v8_debug_helper_shared corruption_harness
make -C tools/debug_helper/plugins test-live-lldb
# To run core tests, first prepare cores, this can take a while
make -C tools/debug_helper/plugins prepare-cores
make -C tools/debug_helper/plugins test-core-lldb
```

On Linux, with `gdb` and `lldb` installed, the output directory is assumed
to be `out/x64.release`. Build and run the tests with:

```sh
autoninja -C out/x64.release d8 v8_debug_helper_shared corruption_harness
make -C tools/debug_helper/plugins test-live
# To run core tests, first prepare cores, this can take a while
make -C tools/debug_helper/plugins prepare-cores
make -C tools/debug_helper/plugins test-core
```

If the output directory is different from the assumed one,
set the `OUT_DIR` environment variable when running the Makefile.

```sh
OUT_DIR="$(pwd)/out/x64.release.test" make -C tools/debug_helper/plugins test-live-lldb
```

## Development Notes

Set `V8_DEBUG_HELPER_VERBOSE=1` to enable verbose logging in the plugins.

To see the raw output from the debugger without assertions, use the `run-*`
targets instead of `test-*`, for example:

```sh
make -C tools/debug_helper/plugins run-live-backtrace-lldb
```

## Directory Layout

- `gdb_plugin.py`: GDB plugin entry point.
- `lldb_plugin.py`: LLDB plugin entry point.
- `v8dbg/`: shared plugin code
  - `shared_bridge.py`: `ctypes` bridge and `DebuggerBridge` class
    (C-ABI plumbing, JS frame annotation).
  - `inspect.py`: `v8 inspect` data model, ctypes -> dataclass conversion,
    and the renderer.
  - `heap_hints.py`: `HeapHints` dataclass and `resolve_heap_hints` for
    populating it from V8 symbols/offsets.
  - `dispatch.py`: hand-rolled parser and dispatcher for the `v8`
    debugger command.
- `test/`
  - `fixtures/`: test scripts and expected annotation fixtures.
  - `helpers/`: Python helpers for the tests
    - `backtrace.py`, `corruptions.py`: shared assertion helpers for the
      backtrace and corruption suites.
    - `session.py`: interactive gdb / lldb session over a pty, with
      marker-based per-command output capture. Used by the `v8 inspect`
      suites to send commands and parse their output.
    - `inspect.py`: structural assertion helpers and fixture-specific
      `check_*` helpers for the `v8 inspect` suites.
    - `utils.py`: test-config dataclasses and subprocess runner.
  - `test_*.py`: one unittest module per (debugger, mode, feature) combo,
    named `test_{gdb,lldb}_{,inspect_}{live,core}.py`. Run them through
    the Makefile (see "How To Test It").

## Design

`libv8_debug_helper` is the dynamic library built by `v8_debug_helper_shared`,
which exposes C APIs whose definitions can be found in
`debug_helper.h`. The `DebuggerBridge` class in `v8dbg/shared_bridge.py`
wraps those APIs in Python via `ctypes` for the debugger plugins
to call into.

```text
  GDB / LLDB UI
    |
    v
  GDB/LLDB Python plugins
    |
    v
  DebuggerBridge API
    |
    v
  libv8_debug_helper
    |
    v
  DebuggerBridge memory accessor callback
    |
    v
  live process or core dump memory
```

The current `DebuggerBridge` API includes:

- `frame_suffix`: takes a frame pointer plus a memory-reading callback and
  returns the JS annotation suffix for that frame when enough V8 metadata
  can be recovered.
- `inspect`: wraps `_v8_debug_helper_GetObjectProperties` and returns a
  decoupled `InspectResult` dataclass that callers can keep references to
  after the C result has been freed.
