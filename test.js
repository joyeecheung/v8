const obj = globalThis;
let i = 0;
class C1 {
  constructor() {
    return obj;
  }
}
class C2 extends C1 {
  field = 'abc' + i++;
}
new C2();
new C2();
Object.seal(obj);
new C2();
