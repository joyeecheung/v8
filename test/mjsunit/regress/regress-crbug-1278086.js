// Copyright 2021 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

class C {
  field = c.concat();
}

var c;
assertThrows(() => {
  c = new C();
}, TypeError);

class D {
  field = ({ d } = undefined);
}

var d;
assertThrows(() => {
  d = new D();
}, TypeError, /Cannot read properties of undefined/);
