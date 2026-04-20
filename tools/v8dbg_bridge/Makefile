GDB ?= gdb
LLDB ?= lldb

ifeq ($(shell uname -s),Darwin)
OUT_DIR ?= ../../out/arm64.release
DEBUG_HELPER_LIB ?= $(OUT_DIR)/libv8_debug_helper.dylib
else
OUT_DIR ?= ../../out/x64.release
DEBUG_HELPER_LIB ?= $(OUT_DIR)/libv8_debug_helper.so
endif

D8 ?= $(dir $(DEBUG_HELPER_LIB))d8
SCRIPT ?= ./test_script.js
GDBINIT ?= ../gdbinit

.PHONY: gdb-test lldb-test test

gdb-test:
	V8_DEBUG_HELPER_LIB_PATH="$(abspath $(DEBUG_HELPER_LIB))" \
	$(GDB) -nx -q -batch \
		-iex 'set debuginfod enabled off' \
		-iex 'source $(abspath $(GDBINIT))' \
		-iex 'source gdb_adapter.py' \
		-ex 'file $(abspath $(D8))' \
		-ex 'break v8::internal::JsonStringify' \
		-ex 'run $(abspath $(SCRIPT))' \
		-ex 'bt'

lldb-test:
	V8_DEBUG_HELPER_LIB_PATH="$(abspath $(DEBUG_HELPER_LIB))" \
	$(LLDB) -b \
		-O 'command script import lldb_adapter.py' \
		-O 'target create $(abspath $(D8))' \
		-O 'breakpoint set --name v8::internal::JsonStringify' \
		-O 'settings set target.run-args $(abspath $(SCRIPT))' \
		-O 'run' \
		-O 'bt'

test: gdb-test lldb-test