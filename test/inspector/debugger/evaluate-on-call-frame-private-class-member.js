// Copyright 2022 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

const {session, contextGroup, Protocol} =
  InspectorTest.start(`Evaluate private class member out of class scope`);

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
    #field = "string";
    get #getterOnly() { return "getterOnly"; }
    set #setterOnly(val) { this.#field = "setterOnlyCalled"; }
    get #accessor() { return this.#field }
    set #accessor(val) { this.#field = val; }
    #method() { return "method"; }
  }
  const obj = new Klass();
  debugger;
  `, 0, 0, 'test.js');

  Protocol.Debugger.enable();
  Protocol.Runtime.evaluate({expression: 'run()'});

  const {params: {callFrames}} = await Protocol.Debugger.oncePaused();
  const frame = callFrames[0];

  InspectorTest.log('checking private fields');
  await runAndLog(frame, 'obj.#field');
  await runAndLog(frame, 'obj.#field = 1');
  await runAndLog(frame, 'obj.#field');
  await runAndLog(frame, 'obj.#field++');
  await runAndLog(frame, 'obj.#field');
  await runAndLog(frame, '++obj.#field');
  await runAndLog(frame, 'obj.#field');
  await runAndLog(frame, 'obj.#field -= 3');
  await runAndLog(frame, 'obj.#field');

  InspectorTest.log('checking private getter-only accessors');
  await runAndLog(frame, 'obj.#getterOnly');
  await runAndLog(frame, 'obj.#getterOnly = 1');
  await runAndLog(frame, 'obj.#getterOnly++');
  await runAndLog(frame, 'obj.#getterOnly -= 3');
  await runAndLog(frame, 'obj.#getterOnly');

  InspectorTest.log('checking private setter-only accessors');
  await runAndLog(frame, 'obj.#setterOnly');
  await runAndLog(frame, 'obj.#setterOnly = 1');
  await runAndLog(frame, 'obj.#setterOnly++');
  await runAndLog(frame, 'obj.#setterOnly -= 3');
  await runAndLog(frame, 'obj.#field');

  InspectorTest.log('checking private accessors');
  await runAndLog(frame, 'obj.#accessor');
  await runAndLog(frame, 'obj.#accessor = 1');
  await runAndLog(frame, 'obj.#field');
  await runAndLog(frame, 'obj.#accessor++');
  await runAndLog(frame, 'obj.#field');
  await runAndLog(frame, '++obj.#accessor');
  await runAndLog(frame, 'obj.#field');
  await runAndLog(frame, 'obj.#accessor -= 3');
  await runAndLog(frame, 'obj.#field');

  InspectorTest.log('checking private methods');
  await runAndLog(frame, 'obj.#method');
  await runAndLog(frame, 'obj.#method = 1');
  await runAndLog(frame, 'obj.#method++');
  await runAndLog(frame, '++obj.#method');
  await runAndLog(frame, 'obj.#method -= 3');

  InspectorTest.completeTest();
})();
