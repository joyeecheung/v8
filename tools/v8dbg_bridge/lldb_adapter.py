import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from debugger_bridge import frame_suffix, lib_path


_DEFAULT_FRAME_FORMAT = (
    "frame #${frame.index}:{ ${frame.no-debug}${frame.pc}}"
    "{ ${module.file.basename}{`${function.name-with-args}{${frame.no-debug}${function.pc-offset}}}}"
    "{ at ${line.file.basename}:${line.number}}"
    "{${function.is-optimized} [opt]}"
)


def _frame_name(frame):
    function_name = frame.GetFunctionName()
    if function_name:
        return function_name
    symbol = frame.GetSymbol()
    if symbol and symbol.IsValid():
        return symbol.GetName() or ""
    return ""


def _should_annotate(frame):
    return "Builtin" in _frame_name(frame)


def _lldb_read_memory(process, address, byte_count):
    error = __import__("lldb").SBError()
    data = process.ReadMemory(address, byte_count, error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "unable to read memory")
    return data


def frame_annotation(frame, _unused):
    try:
        if not _should_annotate(frame):
            return ""
        process = frame.GetThread().GetProcess()
        return frame_suffix(
            frame.GetFP(), lambda address, size: _lldb_read_memory(process, address, size)
        )
    except Exception as exc:
        return f" [annotation-error: {exc}]"


def _frame_format():
    callback = f"${{script.frame:{__name__}.frame_annotation}}"
    return _DEFAULT_FRAME_FORMAT + callback + r"\n"


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(f"settings set frame-format '{_frame_format()}'")
    print(f"Loaded v8dbg frame formatter from {lib_path()}")