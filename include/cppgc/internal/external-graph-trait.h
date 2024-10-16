// Copyright 2024 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef INCLUDE_CPPGC_INTERNAL_EXTERNAL_GRAPH_TRAIT_H_
#define INCLUDE_CPPGC_INTERNAL_EXTERNAL_GRAPH_TRAIT_H_

#include <type_traits>

#include "cppgc/type-traits.h"

namespace v8 {

class EmbedderGraph;
class EmbedderGraph {
 public:
  class Node;
};
}  // namespace v8

namespace cppgc {
namespace internal {

using ExternalGraphCallback = void (*)(v8::EmbedderGraph::Node* self, v8::EmbedderGraph* graph);

}  // namespace internal
}  // namespace cppgc

#endif  // INCLUDE_CPPGC_INTERNAL_FINALIZER_TRAIT_H_
