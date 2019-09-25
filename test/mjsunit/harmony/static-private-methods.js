// Copyright 2019 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Flags: --harmony-private-methods

"use strict";

// Static private methods
{
  let store = 1;
  class C {
    static #a() { return store; }
    static a() { return this.#a(); }
  }
  assertEquals(C.a(), store);
  assertThrows(() => C.a.call(new C), TypeError);
}

// Complementary static private accessors.
{
  let store = 1;
  class C {
    static get #a() { return store; }
    static set #a(val) { store = val; }
    static incA() { this.#a++; }
    static getA() { return this.#a; }
    static setA(val) { this.#a = val; }
  }
  assertEquals(C.getA(), 1);
  C.incA();
  assertEquals(store, 2);
  C.setA(3);
  assertEquals(store, 3);

  assertThrows(() => C.incA.call(new C), TypeError);
  assertThrows(() => C.getA.call(new C), TypeError);
  assertThrows(() => C.setA.call(new C), TypeError);

  assertThrows(() => { const incA = C.incA; incA(); }, TypeError);
  assertThrows(() => { const getA = C.getA; getA(); }, TypeError);
  assertThrows(() => { const setA = C.setA; setA(); }, TypeError);
}

// Nested static private methods.
{
  class Outer {
    #a() { return 'Outer'; }
    a() { return this.#a(); }
    test() {
      return class {
        static #a() { return 'C'; }
        static a() { return this.#a(); }
      };
    }
  }

  const obj = new Outer;
  const C = obj.test();
  assertEquals(C.a(), 'C');
  assertThrows(() => obj.a.call(C), TypeError);
  assertThrows(() => obj.a.call(new C), TypeError);
}

// Super property access in static private methods
{
  class A {
    static a = 1;
  }

  class B extends A {
    static #a() { return super.a; }
    static getA() { return this.#a(); }
  }

  assertEquals(B.getA(), 1);
}

// Invalid super property access in static private methods
{
  class A {
    static #a() { return 1; }
    static getA() { return this.#a(); }
  }

  class B extends A {
    static getA() { return super.getA(); }
  }

  assertThrows(() => B.getA(), TypeError);
}

// Duplicate static private accessors and methods.
{
  assertThrows('class C { static get #a() {} static get #a() {} }', SyntaxError);
  assertThrows('class C { static get #a() {} static #a() {} }', SyntaxError);
  assertThrows('class C { static get #a() {} get #a() {} }', SyntaxError);
  assertThrows('class C { static get #a() {} set #a(val) {} }', SyntaxError);
  assertThrows('class C { static get #a() {} #a() {} }', SyntaxError);

  assertThrows('class C { static set #a(val) {} static set #a(val) {} }', SyntaxError);
  assertThrows('class C { static set #a(val) {} static #a() {} }', SyntaxError);
  assertThrows('class C { static set #a(val) {} get #a() {} }', SyntaxError);
  assertThrows('class C { static set #a(val) {} set #a(val) {} }', SyntaxError);
  assertThrows('class C { static set #a(val) {} #a() {} }', SyntaxError);

  assertThrows('class C { static #a() {} static #a() {} }', SyntaxError);
  assertThrows('class C { static #a() {} #a(val) {} }', SyntaxError);
  assertThrows('class C { static #a() {} set #a(val) {} }', SyntaxError);
  assertThrows('class C { static #a() {} get #a() {} }', SyntaxError);
}
