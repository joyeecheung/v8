# V8 Debugger Bridge Design

## Purpose

This is a proof of concept for surfacing V8-aware debugging information inside
GDB and LLDB for both live and postmortem debugging.

It combines:

- debugger-specific frame formatting hooks
- a shared Python bridge
- the existing `libv8_debug_helper.so` API already used as the foundation for
   `v8windbg`

The current stack trace decorator is only the first consumer. The same bridge
can support richer debugger features later, similar in spirit to the higher-
level debugger integrations built on top of the same helper library.

## Architecture

```text
                    +---------------------------+
                    |      GDB / LLDB UI        |
                    | stack view and other      |
                    | debugger-facing features  |
                    +-------------+-------------+
                                  |
                                  v
                    +---------------------------+
                    | Debugger integration layer|
                    | - frame enumeration       |
                    | - frame pointer access    |
                    | - target memory reads     |
                    | - rendering / interaction |
                    +-------------+-------------+
                                  |
                                  v
                    +---------------------------+
                    |     Shared bridge layer   |
                    | - Python FFI to helper    |
                    | - maps helper results     |
                    | - resolves V8 metadata    |
                    +-------------+-------------+
                                  |
                                  v
                    +---------------------------+
                    |   libv8_debug_helper.so   |
                    | - V8 frame inspection     |
                    | - V8 object inspection    |
                    +-------------+-------------+
                                  |
                                  v
                    +---------------------------+
                    |   Live process or dump    |
                    | - native stack state      |
                    | - V8 frames               |
                    | - V8 heap objects         |
                    +---------------------------+
```

The important boundary is that debugger-specific code stops at frame access,
memory access, and rendering. V8-specific interpretation lives behind the
shared bridge and the existing V8 debug helper.

This mirrors the same layering that `v8windbg` uses: debugger-specific
integration on top, `debug_helper` underneath. The main difference here is that
the integration layer is written in Python because Python is the best-supported
extension surface in both GDB and LLDB.

## Components

### Debugger integration layer

This layer integrates with each debugger's stack rendering path. It:

- gets the current native frame
- extracts the frame pointer
- reads memory from the stopped process
- renders debugger-facing results

### Shared bridge layer

This layer contains the debugger-neutral logic. It:

- loads `libv8_debug_helper.so`
- calls into the helper through Python FFI
- adapts debugger memory reads to the helper callback model
- turns helper results into metadata used by both debuggers

### Native helper library

- `libv8_debug_helper.so`

This is the V8-side inspection library. It understands V8 frame layout and V8
heap objects.

### Debuggee

- a built V8 binary such as `d8`

The same design applies whether the debugger is attached to a live process or
working against postmortem state, as long as the debugger can provide frame
state and memory reads to the bridge.

## Data Flow

1. GDB or LLDB walks the native stack.
2. The debugger adapter selects a frame to annotate.
3. The adapter gets the frame pointer.
4. The adapter passes the frame pointer and a memory-read callback to the
   shared bridge.
5. The shared bridge calls into `libv8_debug_helper.so` through Python FFI.
6. The helper returns the V8 frame data needed for annotation.
7. The shared bridge resolves any additional object-backed metadata it needs.
8. The bridge returns normalized frame metadata.
9. The debugger adapter renders that metadata as an inline suffix in the stack
   frame.

The helper API details are intentionally not repeated here. The bridge uses the
existing frame and object inspection entry points through Python FFI and turns
their results into one small annotation model shared by GDB and LLDB.

That annotation currently carries:

- JS function name
- script name
- source position when available

The current proof of concept uses that metadata to decorate stack frames, but
the same path can support other debugger features later.

## Example Output

### Before bridge decoration

```text
#0  v8::internal::JsonStringify(...)
#1  v8::internal::Builtin_JsonStringify(...)
#2  Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit
#3  Builtins_InterpreterEntryTrampoline
#4  Builtins_InterpreterEntryTrampoline
#5  Builtins_InterpreterEntryTrampoline
```

### After bridge decoration

```text
#0  v8::internal::JsonStringify(...)
#1  v8::internal::Builtin_JsonStringify(...) [<anonymous>]
#2  Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit
#3  Builtins_InterpreterEntryTrampoline [a @ script.js:1:11]
#4  Builtins_InterpreterEntryTrampoline [b @ script.js:2:49]
#5  Builtins_InterpreterEntryTrampoline [<anonymous> @ script.js:1:1]
```

The native stack is still visible. The bridge only adds V8-aware context to
frames where the helper can recover useful metadata.

## Debugger Integration

### GDB

GDB uses:

- a frame filter / frame decorator
- V8's custom unwinder for stack recovery

The unwinder must be sourced first so V8 frames are recovered before the
backtrace is rendered.

### LLDB

LLDB uses:

- `command script import`
- `settings set frame-format ... ${script.frame:...}`

LLDB uses the same shared bridge and only differs in how it hooks into frame
rendering.

## Current Scope

- annotation is appended to normal native backtraces
- the current PoC focuses on stack trace decoration for V8 builtin frames
- the same bridge is intended to support richer debugger features later
- GDB relies on V8's unwinder for better frame recovery
- some `???` frames remain undecorated because the current helper API does not
  return useful JS metadata for them
