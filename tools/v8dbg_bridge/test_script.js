function a() {
  JSON.stringify({firstProp: 12345, secondProp: "bridge"}, function replacer() {});
}

function b() {
  const hello = "hello";
  return a() + hello.length;
}

b();