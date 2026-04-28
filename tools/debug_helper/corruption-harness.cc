// Copyright 2026 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <fstream>
#include <iterator>
#include <memory>
#include <string>

#include "include/libplatform/libplatform.h"
#include "include/v8-array-buffer.h"
#include "include/v8-context.h"
#include "include/v8-exception.h"
#include "include/v8-function.h"
#include "include/v8-initialization.h"
#include "include/v8-isolate.h"
#include "include/v8-primitive.h"
#include "include/v8-script.h"
#include "include/v8-value.h"
#include "src/api/api-inl.h"
#include "src/objects/js-function.h"
#include "src/objects/script.h"
#include "src/objects/shared-function-info.h"

namespace i = v8::internal;

namespace {

struct Options {
  const char* script_path = nullptr;
};

constexpr char kCorruptScriptSourceAndAbortName[] =
    "corruptScriptSourceAndAbort";
constexpr char kCorruptSFIAndAbortName[] = "corruptSFIAndAbort";
constexpr char kInvalidScriptSourceFlag[] = "invalid-script-source";
constexpr char kInvalidSharedFunctionInfoFlag[] =
    "invalid-shared-function-info";
constexpr char kStopMarker[] = "DEBUG_HELPER_CORRUPTION_STOP";
constexpr i::Tagged_t kBogusTaggedValue =
    static_cast<i::Tagged_t>(0x5a5a5a5bULL);

[[noreturn]] void Usage(const char* program, const char* message = nullptr) {
  if (message != nullptr) {
    fprintf(stderr, "%s\n\n", message);
  }
  fprintf(stderr, "Usage: %s <script>\n", program);
  exit(2);
}

[[noreturn]] void FatalConfigurationError(const char* message) {
  fprintf(stderr, "corruption_harness: %s\n", message);
  fflush(stderr);
  exit(2);
}

[[noreturn]] void StopAfterCorruption(const char* corruption_flag) {
  fprintf(stderr, "%s %s\n", kStopMarker, corruption_flag);
  fflush(stderr);
  abort();
}

void ReportException(v8::Isolate* isolate, v8::TryCatch* try_catch) {
  v8::String::Utf8Value exception(isolate, try_catch->Exception());
  const char* message = *exception == nullptr ? "<exception>" : *exception;
  fprintf(stderr, "corruption_harness script failure: %s\n", message);
  fflush(stderr);
}

bool ParseOptions(int argc, char* argv[], Options* options) {
  if (argc < 2) {
    Usage(argv[0]);
  }
  if (argc > 2) {
    Usage(argv[0], "Unexpected argument");
  }
  options->script_path = argv[1];
  return true;
}

bool ReadFile(const char* path, std::string* contents) {
  std::ifstream input(path, std::ios::binary);
  if (!input.is_open()) return false;

  *contents = std::string(std::istreambuf_iterator<char>(input),
                          std::istreambuf_iterator<char>());
  if (!input.good() && !input.eof()) return false;
  return true;
}

i::Tagged<i::JSFunction> GetTargetFunction(
    const v8::FunctionCallbackInfo<v8::Value>& info,
    const char* function_name) {
  if (info.Length() != 1 || !info[0]->IsFunction()) {
    std::string message = function_name;
    message += " requires a single function argument";
    FatalConfigurationError(message.c_str());
  }
  v8::Local<v8::Function> target_function = info[0].As<v8::Function>();
  return i::Cast<i::JSFunction>(*v8::Utils::OpenDirectHandle(*target_function));
}

void CorruptScriptSourceAndAbort(
    const v8::FunctionCallbackInfo<v8::Value>& info) {
  auto target_function =
      GetTargetFunction(info, kCorruptScriptSourceAndAbortName);
  i::Tagged<i::SharedFunctionInfo> shared = target_function->shared();
  if (!i::IsScript(shared->script())) {
    FatalConfigurationError("target function script must be a Script");
  }
  auto script = i::Cast<i::Script>(shared->script());
  script->Relaxed_WriteField<i::Tagged_t>(i::Script::kSourceOffset,
                                          kBogusTaggedValue);
  StopAfterCorruption(kInvalidScriptSourceFlag);
}

void CorruptSFIAndAbort(const v8::FunctionCallbackInfo<v8::Value>& info) {
  auto target_function = GetTargetFunction(info, kCorruptSFIAndAbortName);
  target_function->Relaxed_WriteField<i::Tagged_t>(
      i::JSFunction::kSharedFunctionInfoOffset, kBogusTaggedValue);
  StopAfterCorruption(kInvalidSharedFunctionInfoFlag);
}

void InstallFunction(v8::Isolate* isolate, v8::Local<v8::Context> context,
                     const char* name, v8::FunctionCallback callback) {
  v8::Local<v8::Function> function;
  if (!v8::Function::New(context, callback).ToLocal(&function)) {
    FatalConfigurationError("failed to create helper function");
  }
  v8::Local<v8::String> function_name;
  if (!v8::String::NewFromUtf8(isolate, name, v8::NewStringType::kNormal)
           .ToLocal(&function_name)) {
    FatalConfigurationError("failed to create helper function name");
  }
  if (!context->Global()
           ->Set(context, function_name, function)
           .FromMaybe(false)) {
    FatalConfigurationError("failed to install helper function");
  }
}

void InstallCorruptionFunctions(v8::Isolate* isolate,
                                v8::Local<v8::Context> context) {
  InstallFunction(isolate, context, kCorruptScriptSourceAndAbortName,
                  CorruptScriptSourceAndAbort);
  InstallFunction(isolate, context, kCorruptSFIAndAbortName,
                  CorruptSFIAndAbort);
}

bool RunScript(v8::Isolate* isolate, v8::Local<v8::Context> context,
               const Options& options) {
  std::string source_text;
  if (!ReadFile(options.script_path, &source_text)) {
    fprintf(stderr, "corruption_harness: failed to read script %s\n",
            options.script_path);
    return false;
  }

  v8::TryCatch try_catch(isolate);
  v8::Local<v8::String> source;
  if (!v8::String::NewFromUtf8(isolate, source_text.c_str(),
                               v8::NewStringType::kNormal,
                               static_cast<int>(source_text.size()))
           .ToLocal(&source)) {
    fprintf(stderr, "corruption_harness: failed to create script source\n");
    return false;
  }

  v8::Local<v8::String> resource_name;
  if (!v8::String::NewFromUtf8(isolate, options.script_path,
                               v8::NewStringType::kNormal)
           .ToLocal(&resource_name)) {
    fprintf(stderr,
            "corruption_harness: failed to create script resource name\n");
    return false;
  }

  v8::ScriptOrigin origin(resource_name);
  v8::Local<v8::Script> script;
  if (!v8::Script::Compile(context, source, &origin).ToLocal(&script)) {
    ReportException(isolate, &try_catch);
    return false;
  }

  v8::Local<v8::Value> result;
  if (!script->Run(context).ToLocal(&result)) {
    ReportException(isolate, &try_catch);
    return false;
  }
  return true;
}

}  // namespace

int main(int argc, char* argv[]) {
  Options options;
  ParseOptions(argc, argv, &options);

  if (!v8::V8::InitializeICUDefaultLocation(argv[0])) {
    fprintf(stderr, "Failed to initialize ICU\n");
    return 1;
  }
  v8::V8::InitializeExternalStartupData(argv[0]);
  std::unique_ptr<v8::Platform> platform = v8::platform::NewDefaultPlatform();
  v8::V8::InitializePlatform(platform.get());
  v8::V8::Initialize();

  v8::Isolate::CreateParams create_params;
  create_params.array_buffer_allocator =
      v8::ArrayBuffer::Allocator::NewDefaultAllocator();
  v8::Isolate* isolate = v8::Isolate::New(create_params);
  int exit_code = 0;
  {
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> context = v8::Context::New(isolate);
    v8::Context::Scope context_scope(context);

    InstallCorruptionFunctions(isolate, context);
    if (!RunScript(isolate, context, options)) {
      exit_code = 1;
    }
  }

  isolate->Dispose();
  v8::V8::Dispose();
  v8::V8::DisposePlatform();
  delete create_params.array_buffer_allocator;
  return exit_code;
}
