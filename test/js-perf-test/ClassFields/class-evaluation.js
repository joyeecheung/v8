// Copyright 2021 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
'use strict';

function addBenchmark(name, test, { setup, tearDown } = {}) {
  new BenchmarkSuite(`ClassWithFieldsEvaluation-${name}`, [1000],
    [
      new Benchmark(name, false, false, 0, test, setup, tearDown)
    ]);
}

addBenchmark('SinglePublicField', SinglePublicField, { setUp, tearDown });
addBenchmark('MultiplePublicFields', MultiplePublicFields, { setUp, tearDown });

addBenchmark('SinglePrivateField', SinglePrivateField, { setUp, tearDown });
addBenchmark('MultiplePrivateFields', MultiplePrivateFields, { setUp, tearDown });

let i = 0;
let klass;

function setUp() {
  klass = void 0;
}

function tearDown() {
  if (!((new klass).check()))
    throw new Error(`Check failed`);
}

function SinglePublicField() {
  class SinglePublicFieldClass {
    x = i;

    check() {
      return this.x === i++;
    }
  }
  return (klass = SinglePublicFieldClass);
}


function SinglePrivateField() {
  class SinglePrivateFieldClass {
    #x = i;

    check() {
      return this.#x === i++;
    }
  }
  return (klass = SinglePrivateFieldClass);
}

function MultiplePublicFields() {
  class MultiPublicFieldClass {
    x = i;
    y = i + 1;
    z = i + 2;
    q = i + 3;
    r = i + 4;
    a = i + 5;

    check() {
      return this.x === i++ && this.y === i++ && this.z === i++ && this.q === i++ && this.r === i++ && this.a === i++;
    }
  };
  return (klass = MultiPublicFieldClass);
}

function MultiplePrivateFields() {
  class MultiPrivateFieldClass {
    #x = i;
    #y = i + 1;
    #z = i + 2;
    #q = i + 3;
    #r = i + 4;
    #a = i + 5;

    check() {
      return this.#x === i++ && this.#y === i++ && this.#z === i++ && this.#q === i++ && this.#r === i++ && this.#a === i++;
    }
  }
  return (klass = MultiPrivateFieldClass);
}
