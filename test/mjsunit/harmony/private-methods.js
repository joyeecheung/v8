// Copyright 2018 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Flags: --harmony-private-methods


"use strict";

{
  class C {
    #a() {}
  }
  new C;
}

{
  class C {
    #a() {
      class B {
        #a() {  }
      }
      new B;
    }
  }
  new C;
}

{
  class A {
    #a() { 
      class C extends A {
        #c() { }
      }
      new C;
    }
  }

  new A;
}

{
  const C = class {
    #a() { }
  }
  new C;
}

{
  const C = class {
    #a() { 
      const B = class {
        #a() {  }
      }
      new B;
    }
  }
  new C;
}
