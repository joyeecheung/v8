// Copyright 2021 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
'use strict';

function addBenchmark(name, test, { setup, tearDown } = {}) {
  new BenchmarkSuite(`DefinePublic-${name}`, [1000],
      [
        new Benchmark(name, false, false, 0, test, setup, tearDown)
      ]);
}

addBenchmark('SingleField', SingleField, { setUp, tearDown });
addBenchmark('MultipleFields', MultipleFields, { setUp, tearDown });

let i = 0;
let instance;

function setUp() {
  instance = void 0;
}

function tearDown() {
  if (!instance.check())
    throw new Error(`Check failed`);
}

class SingleFieldClass {
  x = i;

  check() {
    return this.x === i++;
  }
}

function SingleField() {
  return (instance = new SingleFieldClass);
}

class MultiFieldClass {
  x = i;
  y = i+1;
  z = i+2;
  q = i+3;
  r = i+4;
  a = i+5;

  check() {
    return this.x === i++ && this.y === i++ && this.z === i++ && this.q === i++ && this.r === i++ && this.a === i++;
  }
};

function MultipleFields() {
  return (instance = new MultiFieldClass);
}
