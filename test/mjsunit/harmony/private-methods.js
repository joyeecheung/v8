// Copyright 2018 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Flags: --harmony-private-methods --allow-natives-syntax


"use strict";

{
  class C {
    #a(arg) { this.__calledWith = arg; }
    callA(arg) { this.#a(arg); }
    callAIn(obj, arg) { obj.#a(arg); }
  }

  const c = new C;
  const c2 = new C;

  assertEquals(undefined, c.a);
  assertEquals(undefined, c.__calledWith);
  assertEquals(undefined, c2.__calledWith);

  c.callA('c');
  assertEquals('c', c.__calledWith);
  assertEquals(undefined, c2.__calledWith);

  c2.callAIn(c, 'fromC2');
  assertEquals('fromC2', c.__calledWith);
  assertEquals(undefined, c2.__calledWith);

  c2.callA('c2');
  assertEquals('fromC2', c.__calledWith);
  assertEquals('c2', c2.__calledWith);
}

{
  class C {
    constructor() {
      this.__a = 'init';
    }
    set #a(val) {
      this.__a = val;
    }
    setA(val) {
      this.#a = val;
    }
    setAIn(obj, val) {
      obj.#a = val;
    }
  }

  const c = new C;
  assertEquals(undefined, c.a);
  assertEquals('init', c.__a);
  c.setA('c');
  assertEquals('c', c.__a);

  const c2 = new C;
  assertEquals('init', c2.__a);
  c2.setA('c2');
  assertEquals('c2', c2.__a);
  assertEquals('c', c.__a);

  c.setAIn(c2, 'c.setAIn(c2)');
  assertEquals('c.setAIn(c2)', c2.__a);
  assertEquals('c', c.__a);
}

{
  class C {
    constructor() {
      this.__a = 'init';
    }
    getA() {
      return this.#a;
    }
    get #a() {
      return this.__a;
    }
    getAIn(obj) {
      return obj.#a;
    }
    equals(obj) {
      return this.#a === obj.#a;
    }
  }

  const c = new C;
  assertEquals(undefined, c.a);
  assertEquals('init', c.__a);
  assertEquals('init', c.getA());
  c.__a = 'c';
  assertEquals('c', c.__a);
  assertEquals('c', c.getA());

  const c2 = new C;
  assertEquals('init', c2.__a);
  c2.__a = 'c2';

  assertEquals('c2', c2.__a);
  assertEquals('c2', c2.getA());
  assertEquals('c', c.__a);
  assertEquals('c', c.getA());
  assertEquals('c2', c.getAIn(c2));
  assertEquals('c', c2.getAIn(c));
  assertEquals('c', c.getAIn(c));

  assertEquals(false, c.equals(c2));
  c2.__a = 'c';
  assertEquals(true, c.equals(c2));
}

{
  const C = class { a(obj) { return obj.#b() } #b() { return 1; } };
  const c = new C;
  const c2 = new C;
  assertEquals(undefined, c.b);
  assertEquals(1, c.a(c));
  assertEquals(1, c.a(c2));
}
