import os
import sys
import gdb
from gdb.FrameDecorator import FrameDecorator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from debugger_bridge import frame_suffix, lib_path


def _safe_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def _frame_fp(frame):
    for register_name in ("rbp", "fp", "x29"):
        try:
            value = frame.read_register(register_name)
        except Exception:
            continue
        numeric = _safe_int(value)
        if numeric:
            return numeric
    return 0


def _frame_name(base_name, frame):
    if base_name:
        return base_name
    try:
        return frame.name() or ""
    except Exception:
        return ""


def _should_annotate(base_name):
    return not base_name or "Builtin" in base_name


def _read_memory(address, byte_count):
    inferior = gdb.selected_inferior()
    return bytes(inferior.read_memory(address, byte_count))


class V8DbgFrameDecorator(FrameDecorator):
    def __init__(self, frame_obj):
        super().__init__(frame_obj)

    def function(self):
        base_name = super().function()
        frame = self.inferior_frame()
        if not _should_annotate(_frame_name(base_name, frame)):
            return base_name
        suffix = frame_suffix(_frame_fp(frame), _read_memory)
        if not suffix:
            return base_name
        if not base_name:
            return suffix.strip()
        return f"{base_name}{suffix}"


class V8DbgFrameFilter:
    def __init__(self):
        self.name = "v8dbg_bridge"
        self.priority = 100
        self.enabled = True
        gdb.frame_filters[self.name] = self

    def filter(self, frame_iter):
        return (V8DbgFrameDecorator(frame_obj) for frame_obj in frame_iter)


V8DbgFrameFilter()
gdb.write(f"Loaded v8dbg frame filter from {lib_path()}\n")