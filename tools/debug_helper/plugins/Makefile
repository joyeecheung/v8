PYTHON ?= python3
GDB ?= gdb
LLDB ?= lldb

ifeq ($(shell uname -s),Darwin)
OUT_DIR ?= ../../../out/arm64.release
DEBUG_HELPER_LIB ?= $(OUT_DIR)/libv8_debug_helper.dylib
else
OUT_DIR ?= ../../../out/x64.release
DEBUG_HELPER_LIB ?= $(OUT_DIR)/libv8_debug_helper.so
endif

D8 ?= $(dir $(DEBUG_HELPER_LIB))d8
TEST_DIR ?= ./test
SCRIPT ?= $(TEST_DIR)/test_script.js
D8_ARGS ?= --abort-on-uncaught-exception
GDBINIT ?= ../../gdbinit
GDB_PLUGIN ?= ./gdb_plugin.py
LLDB_PLUGIN ?= ./lldb_plugin.py
GDB_CHECK ?= $(TEST_DIR)/test_gdb.py
LLDB_CHECK ?= $(TEST_DIR)/test_lldb.py

.PHONY: gdb-test lldb-test gdb-check lldb-check test

gdb-test:
	V8_DEBUG_HELPER_LIB_PATH="$(abspath $(DEBUG_HELPER_LIB))" \
	$(GDB) -nx -q -batch \
		-iex 'set debuginfod enabled off' \
		-iex 'source $(abspath $(GDBINIT))' \
		-iex 'source $(abspath $(GDB_PLUGIN))' \
		-ex 'file $(abspath $(D8))' \
		-ex 'run $(D8_ARGS) $(abspath $(SCRIPT))' \
		-ex 'bt' \
		-ex 'quit'

lldb-test:
	V8_DEBUG_HELPER_LIB_PATH="$(abspath $(DEBUG_HELPER_LIB))" \
	$(LLDB) -b \
		-O 'command script import $(abspath $(LLDB_PLUGIN))' \
		-O 'target create $(abspath $(D8))' \
		-O 'settings set -- target.run-args $(D8_ARGS) $(abspath $(SCRIPT))' \
		-O 'run' \
		-k 'bt' \
		-k 'quit'

gdb-check:
	$(PYTHON) $(abspath $(GDB_CHECK)) \
		--gdb '$(GDB)' \
		--gdbinit '$(abspath $(GDBINIT))' \
		--plugin '$(abspath $(GDB_PLUGIN))' \
		--d8 '$(abspath $(D8))' \
		--script '$(abspath $(SCRIPT))' \
		--debug-helper-lib '$(abspath $(DEBUG_HELPER_LIB))'

lldb-check:
	$(PYTHON) $(abspath $(LLDB_CHECK)) \
		--lldb '$(LLDB)' \
		--plugin '$(abspath $(LLDB_PLUGIN))' \
		--d8 '$(abspath $(D8))' \
		--script '$(abspath $(SCRIPT))' \
		--debug-helper-lib '$(abspath $(DEBUG_HELPER_LIB))'

test: gdb-check lldb-check
