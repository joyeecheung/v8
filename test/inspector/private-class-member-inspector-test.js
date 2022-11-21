// Copyright 2022 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

PrivateClassMemberInspectorTest = {};

function getSetupScript({ type, testRuntime }) {
  const pause = testRuntime ? '' : 'debugger;'
  if (type === 'private-instance-member' || type === 'private-static-member') {
    const isStatic = type === 'private-static-member';
    const prefix = isStatic ? 'static' : '';
    const receiver = isStatic ? '' : 'const obj = new Klass();';
    const returnValue = isStatic ? 'Klass' : 'obj';
    return `
function run() {
  class Klass {
    ${prefix} #field = "string";
    ${prefix} get #getterOnly() { return "getterOnly"; }
    ${prefix} set #setterOnly(val) { this.#field = "setterOnlyCalled"; }
    ${prefix} get #accessor() { return this.#field }
    ${prefix} set #accessor(val) { this.#field = val; }
    ${prefix} #method() { return "method"; }
  }
  ${receiver}
  ${pause}
  return ${returnValue};
}`;
  }

  if (type !== 'private-conflicting-member') {
    throw new Error('unknown test type');
  }

  return `
function run() {
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
  ${pause};
  return {
    Klass, ClassWithField, ClassWithAccessor, StaticClass
  };
}`;
}

async function testAllPrivateMembers(type, runAndLog) {
  const receiver = type === 'private-instance-member' ? 'obj' : 'Klass';
  InspectorTest.log('checking private fields');
  await runAndLog(`${receiver}.#field`);
  await runAndLog(`${receiver}.#field = 1`);
  await runAndLog(`${receiver}.#field`);
  await runAndLog(`${receiver}.#field++`);
  await runAndLog(`${receiver}.#field`);
  await runAndLog(`++${receiver}.#field`);
  await runAndLog(`${receiver}.#field`);
  await runAndLog(`${receiver}.#field -= 3`);
  await runAndLog(`${receiver}.#field`);

  InspectorTest.log('checking private getter-only accessors');
  await runAndLog(`${receiver}.#getterOnly`);
  await runAndLog(`${receiver}.#getterOnly = 1`);
  await runAndLog(`${receiver}.#getterOnly++`);
  await runAndLog(`${receiver}.#getterOnly -= 3`);
  await runAndLog(`${receiver}.#getterOnly`);

  InspectorTest.log('checking private setter-only accessors');
  await runAndLog(`${receiver}.#setterOnly`);
  await runAndLog(`${receiver}.#setterOnly = 1`);
  await runAndLog(`${receiver}.#setterOnly++`);
  await runAndLog(`${receiver}.#setterOnly -= 3`);
  await runAndLog(`${receiver}.#field`);

  InspectorTest.log('checking private accessors');
  await runAndLog(`${receiver}.#accessor`);
  await runAndLog(`${receiver}.#accessor = 1`);
  await runAndLog(`${receiver}.#field`);
  await runAndLog(`${receiver}.#accessor++`);
  await runAndLog(`${receiver}.#field`);
  await runAndLog(`++${receiver}.#accessor`);
  await runAndLog(`${receiver}.#field`);
  await runAndLog(`${receiver}.#accessor -= 3`);
  await runAndLog(`${receiver}.#field`);

  InspectorTest.log('checking private methods');
  await runAndLog(`${receiver}.#method`);
  await runAndLog(`${receiver}.#method = 1`);
  await runAndLog(`${receiver}.#method++`);
  await runAndLog(`++${receiver}.#method`);
  await runAndLog(`${receiver}.#method -= 3`);
}

async function testConflictingPrivateMembers(runAndLog) {
  await runAndLog(`(new ClassWithField).#name`);
  await runAndLog(`(new ClassWithMethod).#name`);
  await runAndLog(`(new ClassWithAccessor).#name`);
  await runAndLog(`StaticClass.#name`);
  await runAndLog(`(new StaticClass).#name`);
}

async function runPrivateClassMemberTest(Protocol, { type, testRuntime }) {
  let runAndLog;

  if (testRuntime) {
    let spreadResult;
    switch (type) {
      case 'private-instance-member': {
        spreadResult = 'obj';
        break;
      }
      case 'private-static-member': {
        spreadResult = 'Klass';
        break;
      }
      case 'private-conflicting-member': {
        spreadResult = '{ Klass, ClassWithField, ClassWithAccessor, StaticClass }';
        break;
      }
      default:
        throw new Error('unknown test type');
    }
    await Protocol.Runtime.evaluate({ expression: `const ${spreadResult} = run();` });

    runAndLog = async function runAndLog(expression) {
      InspectorTest.log('Running ' + expression);
      const { result: { result } } =
        await Protocol.Runtime.evaluate({
          expression
        });
      InspectorTest.logMessage(result);
    }
  } else {
    Protocol.Debugger.enable();
    Protocol.Runtime.evaluate({ expression: 'run()' });

    const { params: { callFrames } } = await Protocol.Debugger.oncePaused();
    const frame = callFrames[0];

    runAndLog = async function runAndLog(expression) {
      InspectorTest.log('Running ' + expression);
      const { result: { result } } =
        await Protocol.Debugger.evaluateOnCallFrame({
          callFrameId: frame.callFrameId,
          expression
        });
      InspectorTest.logMessage(result);
    }
  }

  switch (type) {
    case 'private-instance-member':
    case 'private-static-member': {
      await testAllPrivateMembers(type, runAndLog);
      break;
    }
    case 'private-conflicting-member': {
      await testConflictingPrivateMembers(runAndLog);
      break;
    }
    default:
      throw new Error('unknown test type');
  }
}

PrivateClassMemberInspectorTest.runTest = function (InspectorTest, options) {
  const { contextGroup, Protocol } = InspectorTest.start(options.message);

  const setupScript = getSetupScript(options);
  contextGroup.addScript(setupScript);

  InspectorTest.runAsyncTestSuite([async function evaluatePrivateMembers() {
    await runPrivateClassMemberTest(Protocol, options);
  }]);
}
