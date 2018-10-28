// Copyright 2018 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Flags: --harmony-private-methods --allow-natives-syntax


"use strict";

{
  class C {
    #a() { return "a"; }
    getA() { return this.#a(); }
  }

  let c = new C;
  assertEquals(undefined, c.a);
  assertEquals("a", c.getA());
}

{
  class C {
    get #a() { return "a"; }
    getA() { return this.#a; }
  }

  let c = new C;
  assertEquals(undefined, c.a);
  assertEquals("a", c.getA());
}

{
  class C {
    constructor() {
      this.test = "test";
    }
    set #a(val) {
      this.test = val;
    }
    setA(val) {
      this.#a = val;
    }
  }

  let c = new C;
  assertEquals(undefined, c.a);
  c.setA("a");
  assertEquals("a", c.test);
}
