// Copyright 2022 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

const {session, contextGroup, Protocol} =
  InspectorTest.start(`Evaluate private class member from super out of class scope`);

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
    static #staticField = "static";
  }
  class Child extends Klass {
    constructor() {
      debugger;
    }
  }
  const obj = new Child;
  `, 0, 0, 'test.js');

  Protocol.Debugger.enable();
  Protocol.Runtime.evaluate({expression: 'run()'});

  const {params: {callFrames}} = await Protocol.Debugger.oncePaused();
  const frame = callFrames[0];
  // This should throw because this is undefined before super() is invoked.
  await runAndLog(frame, 'this.#field');

  // Currently this are still not allowed in debug-evaluate.
  await runAndLog(frame, 'super');
  await runAndLog(frame, 'super.#staticField');

  InspectorTest.completeTest();
})();
