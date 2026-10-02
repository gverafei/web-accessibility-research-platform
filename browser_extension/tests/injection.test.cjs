const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

function factory(origin='https://example.org') {
  const calls=[];
  const context=vm.createContext({URL,location:{origin},window:{stop:()=>calls.push('stop')},
    document:{open:()=>calls.push('open'),write:html=>calls.push(html),close:()=>calls.push('close')}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../injection.js'),'utf8'),context);
  const fn=vm.runInContext('extensionInjection.applyCandidate',context);
  return {calls,apply:vm.runInContext(`(${fn.toString()})`,context)};
}

test('direct injector is standalone and writes the exact stored HTML in the original document',()=>{
  const {calls,apply}=factory();
  const html='<!doctype html><html><body><script>window.example=1</script></body></html>';
  apply(html,'https://example.org/path/');
  assert.deepEqual(calls,['stop','open',html,'close']);
});

test('injector rejects wrong or non-HTTP source origin before touching the document',()=>{
  const {calls,apply}=factory();
  for(const source of ['https://other.example/','file:///tmp/page','javascript:alert(1)']) {
    assert.throws(()=>apply('<html></html>',source),/Reopen the original/);
  }
  assert.deepEqual(calls,[]);
});
