function test_func_1() {
  return test_func_2();
}

function test_func_2() {
  function test_func_3() {
    return test_func_4();
  }

  function test_func_4() {
    throw new Error("v8dbg bridge test failure");
  }

  return test_func_3();
}


test_func_1();