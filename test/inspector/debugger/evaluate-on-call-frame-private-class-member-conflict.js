// Copyright 2022 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

const {session, contextGroup, Protocol} =
  InspectorTest.start(`Evaluate conflicting private class member out of class scope`);

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
    #name = "string";
  }
  class ClassWithField extends Klass {
    #name = "child";
  }
  class ClassWithMethod extends Klass {
    #name() {}
  }
  class ClassWithAccessor extends Klass {
    get #name() {}
    set #name(val) {}
  }
  class StaticClass extends Klass {
    static #name = "child";
  }
  debugger;
  `, 0, 0, 'test.js');

  Protocol.Debugger.enable();
  Protocol.Runtime.evaluate({expression: 'run()'});

  const {params: {callFrames}} = await Protocol.Debugger.oncePaused();
  const frame = callFrames[0];

  await runAndLog(frame, '(new ClassWithField).#name');
  await runAndLog(frame, '(new ClassWithMethod).#name');
  await runAndLog(frame, '(new ClassWithAccessor).#name');
  await runAndLog(frame, 'StaticClass.#name');
  await runAndLog(frame, '(new StaticClass).#name');

  InspectorTest.completeTest();
})();
