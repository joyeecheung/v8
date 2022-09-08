{
  class A extends class {} {
    #a;
    constructor() {
      super();
      this.#a = 1;
    }
  }

  class B extends class {} {
    #a = 1;
    #b = this.#a;
    foo() { return this.#a; }
    bar(v) { this.#b = v; }
    constructor() {
      super();
      this.foo();
      this.bar(3);
    }
  }

  class C extends B {
    #a = 2;
    constructor() {
      (() => super())();
    }
  }

  new A;
  new B;
  new C;
};
