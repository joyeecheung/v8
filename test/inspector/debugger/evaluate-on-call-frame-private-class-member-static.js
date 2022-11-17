// Copyright 2022 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

const {session, contextGroup, Protocol} =
  InspectorTest.start(`Evaluate static private class member out of class scope`);

async function runAndLog(frame, expression) {
  InspectorTest.log('Running ' + expression);
  const { result: { result } } =
    await Protocol.Debugger.evaluateOnCallFrame({
      callFrameId: frame.callFrameId,
      expression
  });
  InspectorTest.logMessage(result);
}

(async () => {
  await Protocol.Debugger.enable();
  contextGroup.addScript(`
  class Klass {
    static #field = "string";
    static get #getterOnly() { return "getterOnly"; }
    static set #setterOnly(val) { this.#field = "setterOnlyCalled"; }
    static get #accessor() { return this.#field }
    static set #accessor(val) { this.#field = val; }
    static #method() { return "method"; }
  }
  debugger;
  `, 0, 0, 'test.js');

  Protocol.Debugger.enable();
  Protocol.Runtime.evaluate({expression: 'run()'});

  const {params: {callFrames}} = await Protocol.Debugger.oncePaused();
  const frame = callFrames[0];

  InspectorTest.log('checking private fields');
  await runAndLog(frame, 'Klass.#field');
  await runAndLog(frame, 'Klass.#field = 1');
  await runAndLog(frame, 'Klass.#field');
  await runAndLog(frame, 'Klass.#field++');
  await runAndLog(frame, 'Klass.#field');
  await runAndLog(frame, '++Klass.#field');
  await runAndLog(frame, 'Klass.#field');
  await runAndLog(frame, 'Klass.#field -= 3');
  await runAndLog(frame, 'Klass.#field');

  InspectorTest.log('checking private getter-only accessors');
  await runAndLog(frame, 'Klass.#getterOnly');
  await runAndLog(frame, 'Klass.#getterOnly = 1');
  await runAndLog(frame, 'Klass.#getterOnly++');
  await runAndLog(frame, 'Klass.#getterOnly -= 3');
  await runAndLog(frame, 'Klass.#getterOnly');

  InspectorTest.log('checking private setter-only accessors');
  await runAndLog(frame, 'Klass.#setterOnly');
  await runAndLog(frame, 'Klass.#setterOnly = 1');
  await runAndLog(frame, 'Klass.#setterOnly++');
  await runAndLog(frame, 'Klass.#setterOnly -= 3');
  await runAndLog(frame, 'Klass.#field');

  InspectorTest.log('checking private accessors');
  await runAndLog(frame, 'Klass.#accessor');
  await runAndLog(frame, 'Klass.#accessor = 1');
  await runAndLog(frame, 'Klass.#field');
  await runAndLog(frame, 'Klass.#accessor++');
  await runAndLog(frame, 'Klass.#field');
  await runAndLog(frame, '++Klass.#accessor');
  await runAndLog(frame, 'Klass.#field');
  await runAndLog(frame, 'Klass.#accessor -= 3');
  await runAndLog(frame, 'Klass.#field');

  InspectorTest.log('checking private methods');
  await runAndLog(frame, 'Klass.#method');
  await runAndLog(frame, 'Klass.#method = 1');
  await runAndLog(frame, 'Klass.#method++');
  await runAndLog(frame, '++Klass.#method');
  await runAndLog(frame, 'Klass.#method -= 3');

  InspectorTest.completeTest();
})();
