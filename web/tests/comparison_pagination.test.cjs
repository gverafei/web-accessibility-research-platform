const {test}=require('node:test');
const assert=require('node:assert/strict');
const {pageState,filterMembers}=require('../app/static/js/comparison_pagination.js');
test('search includes the matched original and its paired candidate',()=>{
    const members=[{text:'https://example.org Original',pair:'site-1'},
        {text:'Candidate saved locally',pair:'site-1'}, {text:'Other page',pair:'site-2'}];
    assert.deepEqual(filterMembers(members,' EXAMPLE.ORG '),members.slice(0,2));
    assert.deepEqual(filterMembers(members,''),members);
    assert.deepEqual(filterMembers(members,'missing'),[]);
});
test('unpaired matches do not include every unpaired page',()=>{
    const members=[{text:'One',pair:''},{text:'Two',pair:''}];
    assert.deepEqual(filterMembers(members,'one'),[members[0]]);
});
test('250 comparison members, 25 at a time',()=>{
    assert.deepEqual(pageState(250,25,2),{page:2,pages:10,start:25,end:50});
});
test('deletion clamps the last page, including empty lists',()=>{
    assert.deepEqual(pageState(24,25,2),{page:1,pages:1,start:0,end:24});
    assert.deepEqual(pageState(0,5,1),{page:1,pages:1,start:0,end:0});
});
test('all supported sizes cover every member once',()=>{
    for(const size of [5,10,20,25,50,100,250,500]) {
        const covered=[];
        for(let page=1;page<=pageState(250,size,1).pages;page++) {
            const state=pageState(250,size,page);
            for(let i=state.start;i<state.end;i++) covered.push(i);
        }
        assert.equal(covered.length,250);
        assert.equal(new Set(covered).size,250);
    }
});
