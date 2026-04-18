import ast
import ctypes
import functools
import os
import re


_LIBRARY = None
_MEMORY_CALLBACK = None

_MEMORY_ACCESS_OK = 0
_MEMORY_ACCESS_INVALID = 1

_STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


class StructProperty(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("type", ctypes.c_char_p),
        ("offset", ctypes.c_size_t),
        ("num_bits", ctypes.c_uint8),
        ("shift_bits", ctypes.c_uint8),
    ]


StructPropertyPointer = ctypes.POINTER(StructProperty)


class ObjectProperty(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("type", ctypes.c_char_p),
        ("address", ctypes.c_uint64),
        ("num_values", ctypes.c_size_t),
        ("size", ctypes.c_size_t),
        ("num_struct_fields", ctypes.c_size_t),
        ("struct_fields", ctypes.POINTER(StructPropertyPointer)),
        ("kind", ctypes.c_int),
    ]


ObjectPropertyPointer = ctypes.POINTER(ObjectProperty)


class ObjectPropertiesResult(ctypes.Structure):
    _fields_ = [
        ("type_check_result", ctypes.c_int),
        ("brief", ctypes.c_char_p),
        ("type", ctypes.c_char_p),
        ("num_properties", ctypes.c_size_t),
        ("properties", ctypes.POINTER(ObjectPropertyPointer)),
        ("num_guessed_types", ctypes.c_size_t),
        ("guessed_types", ctypes.POINTER(ctypes.c_char_p)),
    ]


class StackFrameResult(ctypes.Structure):
    _fields_ = [
        ("num_properties", ctypes.c_size_t),
        ("properties", ctypes.POINTER(ObjectPropertyPointer)),
    ]


class HeapAddresses(ctypes.Structure):
    _fields_ = [
        ("map_space_first_page", ctypes.c_uint64),
        ("old_space_first_page", ctypes.c_uint64),
        ("read_only_space_first_page", ctypes.c_uint64),
        ("any_heap_pointer", ctypes.c_uint64),
        ("metadata_pointer_table", ctypes.c_uint64),
        ("isolate_heap_member_offset", ctypes.c_uint64),
    ]


MemoryAccessor = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t
)


def lib_path():
    override = os.environ.get("V8_DEBUG_HELPER_LIB_PATH")
    if override:
        return os.path.abspath(override)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(
        repo_root, "out.gn", "x64.release", "libv8_debug_helper.so"
    )


def _library():
    global _LIBRARY
    if _LIBRARY is None:
        library = ctypes.CDLL(lib_path())
        library._v8_debug_helper_GetStackFrame.argtypes = [
            ctypes.c_uint64,
            MemoryAccessor,
        ]
        library._v8_debug_helper_GetStackFrame.restype = ctypes.POINTER(
            StackFrameResult
        )
        library._v8_debug_helper_Free_StackFrameResult.argtypes = [
            ctypes.POINTER(StackFrameResult)
        ]
        library._v8_debug_helper_GetObjectProperties.argtypes = [
            ctypes.c_uint64,
            MemoryAccessor,
            ctypes.POINTER(HeapAddresses),
            ctypes.c_char_p,
        ]
        library._v8_debug_helper_GetObjectProperties.restype = ctypes.POINTER(
            ObjectPropertiesResult
        )
        library._v8_debug_helper_Free_ObjectPropertiesResult.argtypes = [
            ctypes.POINTER(ObjectPropertiesResult)
        ]
        _LIBRARY = library
    return _LIBRARY


def _make_memory_accessor(read_memory):
    def callback(address, destination, byte_count):
        try:
            data = read_memory(address, byte_count)
        except Exception:
            return _MEMORY_ACCESS_INVALID
        if len(data) != byte_count:
            return _MEMORY_ACCESS_INVALID
        ctypes.memmove(destination, data, byte_count)
        return _MEMORY_ACCESS_OK

    return MemoryAccessor(callback)


def _result_property_map(result):
    props = {}
    for index in range(result.num_properties):
        prop = result.properties[index].contents
        props[prop.name.decode("utf-8")] = prop
    return props


def _read_pointer_at(read_memory, address, byte_count):
    data = read_memory(address, byte_count)
    return int.from_bytes(data, byteorder="little", signed=False)


def _decode_cstring(value):
    if not value:
        return ""
    return value.decode("utf-8", errors="replace")


def _strip_address_suffix(brief):
    marker = " (0x"
    if marker in brief:
        return brief.rsplit(marker, 1)[0]
    return brief


def _summarize_brief(brief):
    if not brief:
        return ""
    match = _STRING_LITERAL_RE.search(brief)
    if match:
        try:
            return ast.literal_eval(match.group(0))
        except Exception:
            return match.group(0)[1:-1]
    return _strip_address_suffix(brief)


def _describe_heap_object(raw_value, storage_address, read_memory, type_hint=None):
    global _MEMORY_CALLBACK

    _MEMORY_CALLBACK = _make_memory_accessor(read_memory)
    heap_addresses = HeapAddresses(
        0,
        0,
        0,
        int(storage_address) & ((1 << 64) - 1),
        0,
        0,
    )
    hint = None if type_hint is None else type_hint.encode("utf-8")
    result_ptr = _library()._v8_debug_helper_GetObjectProperties(
        int(raw_value) & ((1 << 64) - 1),
        _MEMORY_CALLBACK,
        ctypes.byref(heap_addresses),
        hint,
    )
    if not result_ptr:
        return ""
    try:
        result = result_ptr.contents
        return _summarize_brief(_decode_cstring(result.brief))
    finally:
        _library()._v8_debug_helper_Free_ObjectPropertiesResult(result_ptr)


def _resolve_property_string(props, prop_name, read_memory):
    prop = props.get(prop_name)
    if prop is None or not prop.address or not prop.size:
        return ""
    raw_value = _read_pointer_at(read_memory, prop.address, prop.size)
    return _describe_heap_object(raw_value, prop.address, read_memory)


def _decode_smi32(raw_value):
    signed = ctypes.c_int32(raw_value).value
    return signed >> 1


def _resolve_function_character_offset(props, read_memory):
    prop = props.get("function_character_offset")
    if prop is None or not prop.address or prop.num_struct_fields == 0:
        return None

    fields = {}
    for index in range(prop.num_struct_fields):
        field = prop.struct_fields[index].contents
        fields[field.name.decode("utf-8")] = field

    start_field = fields.get("start")
    if start_field is None:
        return None

    # V8 exposes the source position fields as tagged Smis. In the x64 release
    # build we are testing, each field occupies 4 bytes.
    field_width = 4
    if "end" in fields:
        field_width = max(1, fields["end"].offset - start_field.offset)

    raw_start = int.from_bytes(
        read_memory(prop.address + start_field.offset, field_width),
        byteorder="little",
        signed=False,
    )
    return _decode_smi32(raw_start)


def _line_col_from_offset(source_text, char_offset):
    if not source_text or char_offset is None or char_offset < 0:
        return None
    offset = min(char_offset, len(source_text))
    line = source_text.count("\n", 0, offset) + 1
    last_newline = source_text.rfind("\n", 0, offset)
    column = offset + 1 if last_newline == -1 else offset - last_newline
    return (line, column)


@functools.lru_cache(maxsize=256)
def describe_js_frame(frame_pointer, read_memory):
    raise TypeError("describe_js_frame must be called via uncached wrapper")


def _describe_js_frame_uncached(frame_pointer, read_memory):
    global _MEMORY_CALLBACK

    if not frame_pointer:
        return None

    _MEMORY_CALLBACK = _make_memory_accessor(read_memory)
    result_ptr = _library()._v8_debug_helper_GetStackFrame(
        int(frame_pointer) & ((1 << 64) - 1), _MEMORY_CALLBACK
    )
    if not result_ptr:
        return None
    try:
        result = result_ptr.contents
        props = _result_property_map(result)
        if "currently_executing_jsfunction" not in props:
            return None
        function_name = _resolve_property_string(props, "function_name", read_memory)
        script_name = _resolve_property_string(props, "script_name", read_memory)
        script_source = _resolve_property_string(props, "script_source", read_memory)
        position = _line_col_from_offset(
            script_source, _resolve_function_character_offset(props, read_memory)
        )
        if function_name == "":
            function_name = "<anonymous>"
        return {
            "function_name": function_name,
            "script_name": script_name,
            "position": position,
        }
    finally:
        _library()._v8_debug_helper_Free_StackFrameResult(result_ptr)


def _annotation_key(frame_pointer, read_memory):
    return (int(frame_pointer) & ((1 << 64) - 1), id(read_memory))


@functools.lru_cache(maxsize=256)
def _cached_frame_annotation(frame_pointer, reader_id, read_memory):
    del reader_id
    return _describe_js_frame_uncached(frame_pointer, read_memory)


def describe_js_frame(frame_pointer, read_memory):
    return _cached_frame_annotation(
        int(frame_pointer) & ((1 << 64) - 1), id(read_memory), read_memory
    )


def frame_suffix(frame_pointer, read_memory):
    annotation = describe_js_frame(frame_pointer, read_memory)
    if not annotation:
        return ""
    function_name = annotation.get("function_name") or "<anonymous>"
    script_name = annotation.get("script_name")
    position = annotation.get("position")
    location_suffix = ""
    if position:
        location_suffix = f":{position[0]}:{position[1]}"
    if script_name:
        return f" [{function_name} @ {script_name}{location_suffix}]"
    return f" [{function_name}]"