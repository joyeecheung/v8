// Copyright 2018 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Flags: --harmony-symbol-description

const symbol = Symbol('test');
assertEquals(symbol.description, 'test');

assertFalse(symbol.hasOwnProperty('description'));

let desc = Object.getOwnPropertyDescriptor(Symbol.prototype, 'description');
assertEquals(desc.set, undefined);
assertFalse(!!desc.writable);
assertFalse(desc.enumerable);
assertTrue(desc.configurable);
