from debugger_bridge import _summarize_brief, lib_path


print(lib_path())
print(_summarize_brief('"demo" (0x1234 <v8::internal::SeqOneByteString>)'))
