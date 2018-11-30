// Copyright 2018 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Flags: --harmony-private-methods --allow-natives-syntax


"use strict";

// Basic private method test
{
  let calledWith;
  class C {
    #a(arg) { calledWith = arg; }
    callA(arg) { this.#a(arg); }
  }
  const c = new C;
  assertEquals(undefined, c.a);
  assertEquals(undefined, calledWith);
  c.callA(1);
  assertEquals(1, calledWith);
}

{
  let calledWith;
  class C {
    #a(arg) { calledWith = arg; }
    a(arg) { this.#a(arg); }
  }
  const c = new C;
  c.a(1);
  assertEquals(1, calledWith);
}

// Call private method in another instance
{
  class C {
    #a(arg) { this.calledWith = arg; }
    callAIn(obj, arg) { obj.#a(arg); }
  }

  const c = new C;
  const c2 = new C;

  assertEquals(undefined, c.a);
  assertEquals(undefined, c.calledWith);
  assertEquals(undefined, c2.calledWith);

  c2.callAIn(c, 'fromC2');
  assertEquals('fromC2', c.calledWith);
  assertEquals(undefined, c2.calledWith);

  c2.callAIn(c2, 'c2');
  assertEquals('fromC2', c.calledWith);
  assertEquals('c2', c2.calledWith);
}

// Private setter
{
  class C {
    constructor(a) {
      this.__a = a;
    }
    set #a(val) {
      this.__a = val;
    }
    setA(val) {
      this.#a = val;
    }
  }

  const c = new C('init');
  assertEquals(undefined, c.a);
  assertEquals('init', c.__a);
  c.setA('c');
  assertEquals('c', c.__a);

  const c2 = new C('init');
  assertEquals('init', c2.__a);
  c2.setA('c2');
  assertEquals('c2', c2.__a);
  assertEquals('c', c.__a);
}

// Call private setter in another instance
{
  class C {
    constructor(a) {
      this.__a = a;
    }
    set #a(val) {
      this.__a = val;
    }
    setAIn(obj, val) {
      obj.#a = val;
    }
  }

  const c = new C('init');
  const c2 = new C('init');
  assertEquals(undefined, c.a);
  assertEquals(undefined, c2.a);
  assertEquals('init', c.__a);
  assertEquals('init', c2.__a);

  c.setAIn(c2, 'c.setAIn(c2)');
  assertEquals('c.setAIn(c2)', c2.__a);
  assertEquals('init', c.__a);

  c.setAIn(c, 'c.setAIn(c)');
  assertEquals('c.setAIn(c2)', c2.__a);
  assertEquals('c.setAIn(c)', c.__a);
}

// Private getter and call private getter in another instance
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
  assertEquals('init', c2.getA());
  c2.__a = 'c2';
  assertEquals('c2', c2.getA());

  assertEquals('c', c.__a);
  assertEquals('c', c.getA());
  assertEquals(false, c.equals(c2));
  c2.__a = 'c';
  assertEquals(true, c.equals(c2));
}

// Private methods and private fields
{
  class C {
    #a;
    constructor(a) {
      this.#a = a;
    }
    get #aPlus1() {
      return this.#a + 1;
    }
    getAPlus1() {
      return this.#aPlus1;
    }
    getAPlus1In(obj) {
      return obj.#aPlus1;
    }
    equals(obj) {
      return this.#aPlus1 === obj.#aPlus1;
    }
  }

  const c = new C(0);
  const c2 = new C(2);
  const c3 = new C(2);

  assertEquals(undefined, c.a);
  assertEquals(1, c.getAPlus1());
  assertEquals(3, c.getAPlus1In(c2));
  assertEquals(true, c2.equals(c3));
  assertEquals(false, c2.equals(c));
  assertEquals(false, c3.equals(c));
}

// Class inheritance
{
  class A {
    #val;
    constructor(a) {
      this.#val = a;
    }
    #a() { return this.#val; }
    getA() { return this.#a(); }
  }

  class B extends A {
    constructor(b) {
      super(b);
    }
    b() { return this.getA() }
  }

  const b = new B(1);
  assertEquals(1, b.b());
}


{
  class A {
    #val;
    constructor(a) {
      this.#val = a;
    }
    #getVal() { return this.#val; }
    getA() { return this.#getVal(); }
    getVal() { return this.#getVal(); }
  }

  class B extends A {
    #val;
    constructor(a, b) {
      super(a);
      this.#val = b;
    }
    #getVal() { return this.#val; }
    getB() { return this.#getVal(); }
    getVal() { return this.#getVal(); }
  }

  const b = new B(1, 2);
  assertEquals(1, b.getA());
  assertEquals(2, b.getB());
  assertEquals(1, A.prototype.getVal.call(b));
  assertEquals(2, B.prototype.getVal.call(b));

  const a = new A(1);
  assertEquals(1, a.getA());
  assertThrows(() => B.prototype.getB.call(a), TypeError);
}

// Proxy
{
  class X {
    #x() {}
    x() { this.#x(); };
    callX(obj) { obj.#x(); }
  }

  let handlerCalled = false;
  const x = new X();
  let p = new Proxy(new X, {
    apply(target, thisArg, argumentsList) {
      handlerCalled = true;
      Reflect.apply(target, thisArg, argumentsList);
    }
  });

  assertThrows(() => p.x(), TypeError);
  assertThrows(() => x.callX(p), TypeError);
  assertThrows(() => X.prototype.x.call(p), TypeError);
  assertThrows(() => X.prototype.callX(p), TypeError);
  assertEquals(false, handlerCalled);
}


{
  class X {
    get #x() {}
    getX() { this.#x; };
    getXIn(obj) { return obj.#x; }
  }

  let handlerCalled = false;
  const x = new X();
  let p = new Proxy(new X, {
    get(target, name) {
      handlerCalled = true;
      return target[name];
    },
  });

  assertThrows(() => p.getX(), TypeError);
  assertEquals(true, handlerCalled);
  assertThrows(() => x.getXIn(p), TypeError);
  assertThrows(() => X.prototype.x.getX.call(p), TypeError);
  assertThrows(() => X.prototype.getXIn.call(p), TypeError);
}

{
  class X {
    set #x(x) {}
    setX(x) { this.#x = x; };
    setXIn(obj, x) { obj.#x = x; }
  }

  let handlerCalled = false;
  const x = new X();
  let p = new Proxy(new X, {
    set(target, name, val) {
      handlerCalled = true;
      target[name] = val;
    },
  });

  assertThrows(() => p.setX(1), TypeError);
  assertThrows(() => x.setXIn(p, 1), TypeError);
  assertThrows(() => X.prototype.x.setX.call(p, 1), TypeError);
  assertThrows(() => X.prototype.setXIn.call(p, 1), TypeError);
  assertEquals(false, handlerCalled);
}

{
  const C = class { a(obj) { return obj.#b() } #b() { return 1; } };
  const c = new C;
  const c2 = new C;
  assertEquals(undefined, c.b);
  assertEquals(1, c.a(c));
  assertEquals(1, c.a(c2));
}

// Reference outside of class
{
  class C {
    #a() {}
  }
  assertThrows('new C().#a()');
}

{
  assertThrows('class C { #a = 1; get #a() {} }');
  assertThrows('class C { #a = 1; set #a() {} }');
  assertThrows('class C { #a = 1; #a() {} }');
  assertThrows('class C { #a() {} get #a() {} }');
  // TODO(joyee): implement complementary accessors
}
