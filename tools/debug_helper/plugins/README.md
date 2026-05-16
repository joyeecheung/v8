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
[<function_name>(this=<brief>, <brief>, ...) @ <script_name>:<line>:<column>]
```

The receiver and the first few positional arguments are summarised inline as
`<Smi: 42>`, `<String: "world">`, `<JSObject>`, and so on. To suppress the
brief and fall back to the bare form, set `V8_DEBUG_HELPER_FRAME_BRIEFS=0`:

```
[<function_name> @ <script_name>:<line>:<column>]
```

If source text cannot be recovered but the script name still can, the
annotation degrades to drop the `@ ...` location.

For anonymous functions the name is shown as `<anonymous>`. The line and column
point to the start of the function scope in its definition, which is
normally the `(` of the parameter list (or position 1:1 for the top-level
script scope), not where the function is called, which we cannot
reliably recover in the debugger.

#### `v8 inspect <addr>`

Walks the tagged V8 object at `<addr>` and prints its properties using a
compact, llnode-compatible grammar. Works on both gdb and lldb:

```
(gdb) v8 inspect 0x34f49880471
0x34f49880471:<JSArray: length=3 {
  .map=0x34f49880409:<Map for JSArray>,
  .properties_or_hash=0x34f49880421:<empty FixedArray>,
  .elements=0x34f49880491:<FixedArray: length=3>,
  .length=<Smi: 3>}>
```

Options:

| Flag | Effect |
|---|---|
| `--type <T>` | Type hint when the Map is unreadable (e.g. `v8::internal::JSArray`). |
| `--depth N` | Inline-recursion depth for child references (default 1). |
| `--array-length N` / `-l N` | Per-array element cap (default 16). |
| `--string-length N` | String truncation length (default 80). |

When the object's Map can't be read (partial dump, corrupted memory), the
output falls back to a `<HeapObject [Map inaccessible]>` brief plus a
`could be one of ...` footer with ready-to-paste `--type` suggestions.

`v8 help` lists available subcommands; additional subcommands can be added
without restructuring the surface.

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
- `test-live-*` targets run the same live sessions but also assert the
  expected annotations in Python.
  - `test-core-*` targets run the same assertions but against the prepared
    core files instead of live processes.
  - `test-core` runs core-file test suites on both debuggers.
  - `test-live` runs live test suites on both debuggers.

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

- `shared_bridge.py`: shared `ctypes` bridge and `DebuggerBridge` class.
- `gdb_plugin.py`: GDB plugin entry point.
- `lldb_plugin.py`: LLDB plugin entry point.
- `test/`
  - `fixtures/`: test scripts and expected annotation fixtures.
  - `helpers/`: Python helpers for the tests
  - `test_gdb_live.py`: live-process GDB tests.
  - `test_lldb_live.py`: live-process LLDB tests.
  - `test_gdb_core.py`: core-file GDB tests.
  - `test_lldb_core.py`: core-file LLDB tests.

## Design

`libv8_debug_helper` is the dynamic library built by `v8_debug_helper_shared`,
which exposes C APIs whose definitions can be found in
`debug_helper.h`. The `DebuggerBridge` class in `shared_bridge.py`
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
  can be recovered. The annotation includes per-arg briefs by default; set
  `V8_DEBUG_HELPER_FRAME_BRIEFS=0` to disable them.
- `inspect`: wraps `_v8_debug_helper_GetObjectProperties` and returns a
  decoupled `InspectResult` dataclass that callers can keep references to
  after the C result has been freed.
- `resolve_heap_hints`: walks `v8::internal::g_current_isolate_` ->
  `IsolateGroup` to populate a `HeapHints` struct with
  `metadata_pointer_table` and `isolate_heap_member_offset`. Required for
  correct inspection on compressed-pointer builds.
- `dispatch_v8_command`: argument-parsing/dispatch helper for the `v8`
  command. Plugins forward their post-`v8` argv to it; the shared dispatcher
  routes to subcommand handlers (currently `inspect`, `help`).
