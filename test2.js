const obj = globalThis;
Object.seal(obj);
Object.defineProperty(obj, 'field', { value: 'abc' });

