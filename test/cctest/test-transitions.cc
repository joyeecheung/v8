// Copyright 2014 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "test/cctest/test-transitions.h"

#include <stdlib.h>

#include <utility>

#include "src/api/api-inl.h"
#include "src/codegen/compilation-cache.h"
#include "src/execution/execution.h"
#include "src/heap/factory.h"
#include "src/objects/field-type.h"
#include "src/objects/objects-inl.h"
#include "src/objects/transitions-inl.h"
#include "test/cctest/cctest.h"
#include "test/cctest/heap/heap-utils.h"

namespace v8 {
namespace internal {

TEST(TransitionArray_SimpleFieldTransitions) {
  CcTest::InitializeVM();
  v8::HandleScope scope(CcTest::isolate());
  Isolate* isolate = CcTest::i_isolate();
  Factory* factory = isolate->factory();

  DirectHandle<String> name1 = factory->InternalizeUtf8String("foo");
  DirectHandle<String> name2 = factory->InternalizeUtf8String("bar");
  PropertyAttributes attributes = NONE;

  DirectHandle<Map> map0 = Map::Create(isolate, 0);
  DirectHandle<Map> map1 =
      Map::CopyWithField(isolate, map0, name1, FieldType::Any(isolate),
                         attributes, PropertyConstness::kMutable,
                         Representation::Tagged(), OMIT_TRANSITION)
          .ToHandleChecked();
  DirectHandle<Map> map2 =
      Map::CopyWithField(isolate, map0, name2, FieldType::Any(isolate),
                         attributes, PropertyConstness::kMutable,
                         Representation::Tagged(), OMIT_TRANSITION)
          .ToHandleChecked();

  CHECK(IsSmi(map0->raw_transitions()));

  {
    TransitionsAccessor::Insert(isolate, map0, name1, map1,
                                SIMPLE_PROPERTY_TRANSITION);
  }
  {
    {
      TestTransitionsAccessor transitions(isolate, map0);
      CHECK(transitions.IsWeakRefEncoding());
      CHECK_EQ(*map1, transitions.SearchTransition(*name1, PropertyKind::kData,
                                                   attributes));
      CHECK_EQ(1, transitions.NumberOfTransitions());
      CHECK_EQ(*name1, transitions.GetKey(0));
      CHECK_EQ(*map1, transitions.GetTarget(0));
    }

    TransitionsAccessor::Insert(isolate, map0, name2, map2,
                                SIMPLE_PROPERTY_TRANSITION);
  }
  {
    TestTransitionsAccessor transitions(isolate, map0);
    CHECK(transitions.IsFullTransitionArrayEncoding());

    CHECK_EQ(*map1, transitions.SearchTransition(*name1, PropertyKind::kData,
                                                 attributes));
    CHECK_EQ(*map2, transitions.SearchTransition(*name2, PropertyKind::kData,
                                                 attributes));
    CHECK_EQ(2, transitions.NumberOfTransitions());
    for (int i = 0; i < 2; i++) {
      Tagged<Name> key = transitions.GetKey(i);
      Tagged<Map> target = transitions.GetTarget(i);
      CHECK((key == *name1 && target == *map1) ||
            (key == *name2 && target == *map2));
    }

    DCHECK(transitions.IsSortedNoDuplicates());
  }
}


TEST(TransitionArray_FullFieldTransitions) {
  CcTest::InitializeVM();
  v8::HandleScope scope(CcTest::isolate());
  Isolate* isolate = CcTest::i_isolate();
  Factory* factory = isolate->factory();

  DirectHandle<String> name1 = factory->InternalizeUtf8String("foo");
  DirectHandle<String> name2 = factory->InternalizeUtf8String("bar");
  PropertyAttributes attributes = NONE;

  DirectHandle<Map> map0 = Map::Create(isolate, 0);
  DirectHandle<Map> map1 =
      Map::CopyWithField(isolate, map0, name1, FieldType::Any(isolate),
                         attributes, PropertyConstness::kMutable,
                         Representation::Tagged(), OMIT_TRANSITION)
          .ToHandleChecked();
  DirectHandle<Map> map2 =
      Map::CopyWithField(isolate, map0, name2, FieldType::Any(isolate),
                         attributes, PropertyConstness::kMutable,
                         Representation::Tagged(), OMIT_TRANSITION)
          .ToHandleChecked();

  CHECK(IsSmi(map0->raw_transitions()));

  {
    TransitionsAccessor::Insert(isolate, map0, name1, map1,
                                PROPERTY_TRANSITION);
  }
  {
    {
      TestTransitionsAccessor transitions(isolate, map0);
      CHECK(transitions.IsFullTransitionArrayEncoding());
      CHECK_EQ(*map1, transitions.SearchTransition(*name1, PropertyKind::kData,
                                                   attributes));
      CHECK_EQ(1, transitions.NumberOfTransitions());
      CHECK_EQ(*name1, transitions.GetKey(0));
      CHECK_EQ(*map1, transitions.GetTarget(0));
    }

    TransitionsAccessor::Insert(isolate, map0, name2, map2,
                                PROPERTY_TRANSITION);
  }
  {
    TestTransitionsAccessor transitions(isolate, map0);
    CHECK(transitions.IsFullTransitionArrayEncoding());

    CHECK_EQ(*map1, transitions.SearchTransition(*name1, PropertyKind::kData,
                                                 attributes));
    CHECK_EQ(*map2, transitions.SearchTransition(*name2, PropertyKind::kData,
                                                 attributes));
    CHECK_EQ(2, transitions.NumberOfTransitions());
    for (int i = 0; i < 2; i++) {
      Tagged<Name> key = transitions.GetKey(i);
      Tagged<Map> target = transitions.GetTarget(i);
      CHECK((key == *name1 && target == *map1) ||
            (key == *name2 && target == *map2));
    }

    DCHECK(transitions.IsSortedNoDuplicates());
  }
}


TEST(TransitionArray_DifferentFieldNames) {
  CcTest::InitializeVM();
  v8::HandleScope scope(CcTest::isolate());
  Isolate* isolate = CcTest::i_isolate();
  Factory* factory = isolate->factory();

  const int PROPS_COUNT = 10;
  Handle<String> names[PROPS_COUNT];
  Handle<Map> maps[PROPS_COUNT];
  PropertyAttributes attributes = NONE;

  DirectHandle<Map> map0 = Map::Create(isolate, 0);
  CHECK(IsSmi(map0->raw_transitions()));

  for (int i = 0; i < PROPS_COUNT; i++) {
    base::EmbeddedVector<char, 64> buffer;
    SNPrintF(buffer, "prop%d", i);
    Handle<String> name = factory->InternalizeUtf8String(buffer.begin());
    Handle<Map> map =
        Map::CopyWithField(isolate, map0, name, FieldType::Any(isolate),
                           attributes, PropertyConstness::kMutable,
                           Representation::Tagged(), OMIT_TRANSITION)
            .ToHandleChecked();
    names[i] = name;
    maps[i] = map;

    TransitionsAccessor::Insert(isolate, map0, name, map, PROPERTY_TRANSITION);
  }

  TransitionsAccessor transitions(isolate, *map0);
  for (int i = 0; i < PROPS_COUNT; i++) {
    CHECK_EQ(*maps[i], transitions.SearchTransition(
                           *names[i], PropertyKind::kData, attributes));
  }
  for (int i = 0; i < PROPS_COUNT; i++) {
    Tagged<Name> key = transitions.GetKey(i);
    Tagged<Map> target = transitions.GetTarget(i);
    for (int j = 0; j < PROPS_COUNT; j++) {
      if (*names[i] == key) {
        CHECK_EQ(*maps[i], target);
        break;
      }
    }
  }

  DCHECK(transitions.IsSortedNoDuplicates());
}


TEST(TransitionArray_SameFieldNamesDifferentAttributesSimple) {
  CcTest::InitializeVM();
  v8::HandleScope scope(CcTest::isolate());
  Isolate* isolate = CcTest::i_isolate();
  Factory* factory = isolate->factory();

  DirectHandle<Map> map0 = Map::Create(isolate, 0);
  CHECK(IsSmi(map0->raw_transitions()));

  const int ATTRS_COUNT = (READ_ONLY | DONT_ENUM | DONT_DELETE) + 1;
  static_assert(ATTRS_COUNT == 8);
  Handle<Map> attr_maps[ATTRS_COUNT];
  DirectHandle<String> name = factory->InternalizeUtf8String("foo");

  // Add transitions for same field name but different attributes.
  for (int i = 0; i < ATTRS_COUNT; i++) {
    auto attributes = PropertyAttributesFromInt(i);

    Handle<Map> map =
        Map::CopyWithField(isolate, map0, name, FieldType::Any(isolate),
                           attributes, PropertyConstness::kMutable,
                           Representation::Tagged(), OMIT_TRANSITION)
            .ToHandleChecked();
    attr_maps[i] = map;

    TransitionsAccessor::Insert(isolate, map0, name, map, PROPERTY_TRANSITION);
  }

  // Ensure that transitions for |name| field are valid.
  TransitionsAccessor transitions(isolate, *map0);
  for (int i = 0; i < ATTRS_COUNT; i++) {
    auto attributes = PropertyAttributesFromInt(i);
    CHECK_EQ(*attr_maps[i], transitions.SearchTransition(
                                *name, PropertyKind::kData, attributes));
    // All transitions use the same key, so this check doesn't need to
    // care about ordering.
    CHECK_EQ(*name, transitions.GetKey(i));
  }

  DCHECK(transitions.IsSortedNoDuplicates());
}


TEST(TransitionArray_SameFieldNamesDifferentAttributes) {
  CcTest::InitializeVM();
  v8::HandleScope scope(CcTest::isolate());
  Isolate* isolate = CcTest::i_isolate();
  Factory* factory = isolate->factory();

  const int PROPS_COUNT = 10;
  Handle<String> names[PROPS_COUNT];
  Handle<Map> maps[PROPS_COUNT];

  DirectHandle<Map> map0 = Map::Create(isolate, 0);
  CHECK(IsSmi(map0->raw_transitions()));

  // Some number of fields.
  for (int i = 0; i < PROPS_COUNT; i++) {
    base::EmbeddedVector<char, 64> buffer;
    SNPrintF(buffer, "prop%d", i);
    Handle<String> name = factory->InternalizeUtf8String(buffer.begin());
    Handle<Map> map =
        Map::CopyWithField(isolate, map0, name, FieldType::Any(isolate), NONE,
                           PropertyConstness::kMutable,
                           Representation::Tagged(), OMIT_TRANSITION)
            .ToHandleChecked();
    names[i] = name;
    maps[i] = map;

    TransitionsAccessor::Insert(isolate, map0, name, map, PROPERTY_TRANSITION);
  }

  const int ATTRS_COUNT = (READ_ONLY | DONT_ENUM | DONT_DELETE) + 1;
  static_assert(ATTRS_COUNT == 8);
  Handle<Map> attr_maps[ATTRS_COUNT];
  DirectHandle<String> name = factory->InternalizeUtf8String("foo");

  // Add transitions for same field name but different attributes.
  for (int i = 0; i < ATTRS_COUNT; i++) {
    auto attributes = PropertyAttributesFromInt(i);

    Handle<Map> map =
        Map::CopyWithField(isolate, map0, name, FieldType::Any(isolate),
                           attributes, PropertyConstness::kMutable,
                           Representation::Tagged(), OMIT_TRANSITION)
            .ToHandleChecked();
    attr_maps[i] = map;

    TransitionsAccessor::Insert(isolate, map0, name, map, PROPERTY_TRANSITION);
  }

  // Ensure that transitions for |name| field are valid.
  TransitionsAccessor transitions(isolate, *map0);
  for (int i = 0; i < ATTRS_COUNT; i++) {
    auto attr = PropertyAttributesFromInt(i);
    CHECK_EQ(*attr_maps[i],
             transitions.SearchTransition(*name, PropertyKind::kData, attr));
  }

  // Ensure that info about the other fields still valid.
  CHECK_EQ(PROPS_COUNT + ATTRS_COUNT, transitions.NumberOfTransitions());
  for (int i = 0; i < PROPS_COUNT + ATTRS_COUNT; i++) {
    Tagged<Name> key = transitions.GetKey(i);
    Tagged<Map> target = transitions.GetTarget(i);
    if (key == *name) {
      // Attributes transition.
      PropertyAttributes attributes =
          target->GetLastDescriptorDetails(isolate).attributes();
      CHECK_EQ(*attr_maps[static_cast<int>(attributes)], target);
    } else {
      for (int j = 0; j < PROPS_COUNT; j++) {
        if (*names[j] == key) {
          CHECK_EQ(*maps[j], target);
          break;
        }
      }
    }
  }

  DCHECK(transitions.IsSortedNoDuplicates());
}

TEST(TransitionArray_InsertionAfterLinearThreshold) {
  CcTest::InitializeVM();
  v8::Isolate* isolate = CcTest::isolate();
  Isolate* i_isolate = CcTest::i_isolate();
  v8::HandleScope scope(isolate);

  struct Entry {
    enum Kind { kString, kSymbol, kFrozen } kind;
    const char* name;  // for kString and kSymbol (description)
    enum Strongness { kWeak, kStrong } strong;  // keep object alive across GC
  };

  auto OneByte = [isolate](const char* s) {
    return v8::String::NewFromOneByte(isolate,
                                      reinterpret_cast<const uint8_t*>(s),
                                      v8::NewStringType::kNormal)
        .ToLocalChecked();
  };

  v8::Local<v8::Context> context = isolate->GetCurrentContext();
  v8::Local<v8::Value> null_value = v8::Null(isolate);
  // Helper to perform insertions given entries and retain selected handles.
  auto InsertEntries = [&](const std::vector<Entry>& list,
                           std::vector<v8::Global<v8::Object>>& out_handles) {
    v8::HandleScope inner(isolate);
    for (const auto& e : list) {
      v8::Local<v8::Object> obj = v8::Object::New(isolate);
      switch (e.kind) {
        case Entry::kString: {
          v8::Local<v8::String> key = OneByte(e.name);
          obj->Set(context, key, null_value).Check();
          break;
        }
        case Entry::kSymbol: {
          v8::Local<v8::String> desc = OneByte(e.name);
          v8::Local<v8::Symbol> sym = v8::Symbol::New(isolate, desc);
          obj->Set(context, sym, null_value).Check();
          break;
        }
        case Entry::kFrozen: {
          CHECK(obj->SetIntegrityLevel(context, v8::IntegrityLevel::kFrozen)
                    .FromMaybe(false));
          break;
        }
      }
      if (e.strong == Entry::kStrong) out_handles.emplace_back(isolate, obj);
    }
  };

  std::vector<v8::Global<v8::Object>> handles;
  // Get the cached map of the empty object.
  v8::Local<v8::Object> empty = v8::Object::New(isolate);
  Handle<Map> first_map =
      handle(v8::Utils::OpenHandle(*empty)->map(), i_isolate);

  std::vector<Entry> entries = {
      {Entry::kString, "primordials", Entry::kStrong},
      {Entry::kString, "arrow_message_private_symbol", Entry::kStrong},
      {Entry::kString, "fs_use_promises_symbol", Entry::kStrong},
      {Entry::kSymbol, "Symbol.toStringTag", Entry::kWeak},
      {Entry::kString, "constructor", Entry::kWeak},
      {Entry::kString, "node", Entry::kStrong},
      {Entry::kString, "name", Entry::kStrong},
      {Entry::kString, "kNoFailure", Entry::kStrong},
      {Entry::kString, "kPending", Entry::kStrong},
      {Entry::kString, "ERR_ACCESS_DENIED", Entry::kWeak},
      {Entry::kString, "kInit", Entry::kStrong},
      {Entry::kString, "NONE", Entry::kStrong},
      {Entry::kString, "array", Entry::kStrong},
      {Entry::kString, "kPromiseRejectWithNoHandler", Entry::kStrong},
      {Entry::kString, "kAllowedInEnvvar", Entry::kStrong},
      {Entry::kString, "kNoOp", Entry::kStrong},
      {Entry::kString, "isArgumentsObject", Entry::kStrong},
      {Entry::kString, "runDeserializeCallbacks", Entry::kStrong},
      {Entry::kString, "addDeserializeCallback", Entry::kStrong},
      {Entry::kString, "MAX_LENGTH", Entry::kStrong},
      {Entry::kString, "", Entry::kWeak},
      {Entry::kFrozen, nullptr, Entry::kStrong},  // frozen_symbol present
      {Entry::kString, "hasRejectionToWarn", Entry::kStrong},
      {Entry::kString, "SUMMARY", Entry::kStrong},
      {Entry::kString, "mode", Entry::kStrong},
      {Entry::kString, "DEFAULT", Entry::kStrong},
      {Entry::kString, "measureMemory", Entry::kStrong},
      {Entry::kString, "emitWarning", Entry::kStrong},
      {Entry::kString, "encode", Entry::kWeak},
      {Entry::kString, "encoding", Entry::kWeak},
      {Entry::kString, "recursive", Entry::kStrong},
      {Entry::kSymbol, "kBindStreamsEager", Entry::kWeak},
      {Entry::kString, "Console", Entry::kStrong},
      {Entry::kString, "NODE_PERFORMANCE_GC_MAJOR", Entry::kStrong},
      {Entry::kString, "NONE", Entry::kStrong},  // Duplicate
      {Entry::kString, "addEventListener", Entry::kStrong},
  };
  CHECK_GT(static_cast<int>(entries.size()),
           TransitionArray::kMaxElementsForLinearSearch);
  // const int strong_count = static_cast<int>(
  //     std::count_if(entries.begin(), entries.end(),
  //                   [](const Entry& e) { return e.strong == Entry::kStrong; }));

  InsertEntries(entries, handles);
  {
    TestTransitionsAccessor transitions(i_isolate, first_map);
    CHECK_EQ(static_cast<int>(entries.size()) - 1,
             transitions.NumberOfTransitions());
    CHECK(transitions.transitions()->IsSortedNoDuplicates());
  }

  // Collect garbage to drop dead transitions and then add the rest.
  heap::InvokeMajorGC(CcTest::heap());

  {
    TestTransitionsAccessor transitions(i_isolate, first_map);
    // CHECK_EQ(strong_count, transitions.NumberOfTransitions());
    CHECK(transitions.transitions()->IsSortedNoDuplicates());
  }

  std::vector<Entry> extra = {
      {Entry::kSymbol, "realpathCacheKey", Entry::kStrong},
      {Entry::kString, "constructor", Entry::kStrong},
      {Entry::kString, "addAbortSignal", Entry::kStrong},
      {Entry::kString, "StringDecoder", Entry::kStrong},
      {Entry::kString, "streamReturningOperators", Entry::kStrong},
      {Entry::kString, "SOCKET", Entry::kStrong},
  };
  InsertEntries(extra, handles);

  {
    TestTransitionsAccessor transitions(i_isolate, first_map);
    // const int expected = strong_count + static_cast<int>(extra.size());
    // CHECK_EQ(expected, transitions.NumberOfTransitions());
    Print(transitions.transitions());
    CHECK(transitions.transitions()->IsSortedNoDuplicates());
  }
}

}  // namespace internal
}  // namespace v8
