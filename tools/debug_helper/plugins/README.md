# V8 Debug Helper Plugins

This directory contains Python debugger plugins that load
`libv8_debug_helper` to facilitate post-mortem and live debugging of V8 frames and objects in GDB and LLDB.

## How To Build It

Build the shared debug helper library from the repository root:

```sh
autoninja -C out/<config> v8_debug_helper_shared
```

The plugins load the library from the `V8_DEBUG_HELPER_LIB_PATH`
environment variable.

## How To Use It

First set `V8_DEBUG_HELPER_LIB_PATH` environment variable to the built shared library.

For GDB, run the following commands:

```sh
source tools/gdbinit
source tools/debug_helper/plugins/gdb_plugin.py
```

For LLDB:

```sh
command script import tools/debug_helper/plugins/lldb_plugin.py
```

### Current features

The plugins currently only annotate V8 frames in backtraces, but the bridge can support more features later.

Once loaded, the plugins append JavaScript annotations to candidate V8 frames
when you print a backtrace. The annotation format is:

```
[<function_name> @ <script_name>:<line>:<column>]
```

For anonymous functions the name is shown as `<anonymous>`. The line and column
point to the `function` keyword of the **definition** (or position 1:1 for the
top-level script scope) of the function, not the callsite.

## How To Test It

Before running the debugger tests, build both `d8` and
`v8_debug_helper_shared` in the same output directory:

```sh
autoninja -C out/<config> d8 v8_debug_helper_shared
```

The Makefile resolves both binaries from `OUT_DIR` relative to the plugin
directory, so when invoking it from the repository root pass an absolute path:

```sh
OUT_DIR="$(pwd)/out/<config>" make -C tools/debug_helper/plugins gdb-test
OUT_DIR="$(pwd)/out/<config>" make -C tools/debug_helper/plugins lldb-test
```

To assert the annotations instead of only printing a backtrace:

```sh
OUT_DIR="$(pwd)/out/<config>" make -C tools/debug_helper/plugins gdb-check
OUT_DIR="$(pwd)/out/<config>" make -C tools/debug_helper/plugins lldb-check
OUT_DIR="$(pwd)/out/<config>" make -C tools/debug_helper/plugins test
```

The test fixture is `test/throw.js`. It should be run with
`d8 --abort-on-uncaught-exception` to stop on a nested throw so the harnesses
can check the annotated frames.

## Directory Layout

- `shared_bridge.py`: shared `ctypes` bridge and `DebuggerBridge` class.
- `gdb_plugin.py`: GDB entry point.
- `lldb_plugin.py`: LLDB entry point.
- `test/check_annotations.py`: shared helpers for validating plugin output.
- `test/test_gdb.py`: GDB assertion harness.
- `test/test_lldb.py`: LLDB assertion harness.
- `test/throw.js`: JavaScript crash fixture used by the debugger tests.

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

- `frame_suffix`: which takes the frame pointer and a callback for reading memory, and returns a string annotation for the frame if it's a V8 frame.
  - It uses `_v8_debug_helper_GetStackFrame` to get the frame structure,
    then reads source information using `_v8_debug_helper_GetObjectProperties` to format the annotation string.
