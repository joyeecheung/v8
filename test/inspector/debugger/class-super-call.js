// Copyright 2023 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

const {
  session, contextGroup, Protocol
} = InspectorTest.start('Evaluate super() in derived class constructor');

const script = `
class Base {
  constructor() {
    this.x = 1;
  }
}

let testString;
class ChildWithContext extends Base {
  constructor() {
    testString = 'ChildWithContext breakpoint';
    function forceContext() {
      return eval("force context");
    };
  }
}

class ChildWithoutContext extends Base {
  constructor() {
    testString = 'ChildWithoutContext breakpoint';
  }
}

class Dummy {
  constructor(fn) {
    fn();
  }
}

class ChildWithArrow extends Base {
  constructor() {
    new Dummy(() => {
      testString = 'ChildWithArrow breakpoint';
    });
  }
}

class ChildWithArrowAndContext extends Base {
  constructor() {
    new Dummy(() => {
      testString = 'ChildWithArrowAndContext breakpoint';
    });
    function forceContext() {
      return eval("force context");
    };
  }
}
`;
session.setupScriptMap();
const url = 'test.js';
contextGroup.addScript(script, 0, 0, url);

const lines = script.split('\n');
function getBreakPoint(marker) {
  for (let i = 0; i < lines.length; ++i) {
    if (lines[i].includes(marker)) {
      return {lineNumber: i, url: url}
    }
  }
}

InspectorTest.runAsyncTestSuite([
  async function testScopesPaused() {
    Protocol.Debugger.enable();
    Protocol.Runtime.enable();

    // {
    //   InspectorTest.log('Testing ChildWithContext');
    //   let breakpoint = getBreakPoint('ChildWithContext breakpoint');
    //   let { result: {locations} } =
    //     await Protocol.Debugger.setBreakpointByUrl(breakpoint);
    //   InspectorTest.log('Setting breakpoint and invoke constructor');
    //   await session.logSourceLocation(locations[0]);
    //   Protocol.Runtime.evaluate({ expression: 'new ChildWithContext()' });
    //   let { params: { callFrames } } = await Protocol.Debugger.oncePaused();
    //   InspectorTest.log('Evaluate super()');
    //   let { result: { result } } = await Protocol.Debugger.evaluateOnCallFrame({
    //     callFrameId: callFrames[0].callFrameId,
    //     expression: "super()"
    //   });
    //   InspectorTest.log('Result of super()');
    //   InspectorTest.logObject(result);
    //   await Protocol.Debugger.resume();
    // }

    // {
    //   InspectorTest.log('\nTesting ChildWithoutContext');
    //   let breakpoint = getBreakPoint('ChildWithoutContext breakpoint');
    //   let { result: {locations} } =
    //     await Protocol.Debugger.setBreakpointByUrl(breakpoint);
    //   InspectorTest.log('Setting breakpoint and invoke constructor');
    //   await session.logSourceLocation(locations[0]);
    //   Protocol.Runtime.evaluate({ expression: 'new ChildWithoutContext()' });
    //   let { params: { callFrames } } = await Protocol.Debugger.oncePaused();
    //   InspectorTest.log('Evaluate super()');
    //   let { result: { result } } = await Protocol.Debugger.evaluateOnCallFrame({
    //     callFrameId: callFrames[0].callFrameId,
    //     expression: "super()"
    //   });
    //   InspectorTest.log('Result of super()');
    //   InspectorTest.logObject(result);
    //   await Protocol.Debugger.resume();
    // }

    {
      InspectorTest.log('\nTesting ChildWithArrow');
      let breakpoint = getBreakPoint('ChildWithArrow breakpoint');
      let { result: {locations} } =
        await Protocol.Debugger.setBreakpointByUrl(breakpoint);
      InspectorTest.log('Setting breakpoint and invoke constructor');
      await session.logSourceLocation(locations[0]);
      Protocol.Runtime.evaluate({ expression: 'new ChildWithArrow()' });
      let { params: { callFrames } } = await Protocol.Debugger.oncePaused();
      InspectorTest.log('Evaluate super()');
      let { result: { result } } = await Protocol.Debugger.evaluateOnCallFrame({
        callFrameId: callFrames[0].callFrameId,
        expression: "super()"
      });
      InspectorTest.log('Result of super()');
      InspectorTest.logObject(result);
      await Protocol.Debugger.resume();
    }

    // {
    //   InspectorTest.log('\nTesting ChildWithArrowAndContext');
    //   let breakpoint = getBreakPoint('ChildWithArrowAndContext breakpoint');
    //   let { result: {locations} } =
    //     await Protocol.Debugger.setBreakpointByUrl(breakpoint);
    //   InspectorTest.log('Setting breakpoint and invoke constructor');
    //   await session.logSourceLocation(locations[0]);
    //   Protocol.Runtime.evaluate({ expression: 'new ChildWithArrowAndContext()' });
    //   let { params: { callFrames } } = await Protocol.Debugger.oncePaused();
    //   InspectorTest.log('Evaluate super()');
    //   let { result: { result } } = await Protocol.Debugger.evaluateOnCallFrame({
    //     callFrameId: callFrames[0].callFrameId,
    //     expression: "super()"
    //   });
    //   InspectorTest.log('Result of super()');
    //   InspectorTest.logObject(result);
    //   await Protocol.Debugger.resume();
    // }

    await Protocol.Debugger.disable();
  }
]);
