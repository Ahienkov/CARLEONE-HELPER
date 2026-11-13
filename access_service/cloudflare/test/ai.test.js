import assert from 'node:assert/strict';
import {before,after,beforeEach,test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Miniflare,Response} from 'miniflare';
let mf,db,calls,hold,fail,reply;
const settings={modules:true,scriptPath:fileURLToPath(new URL('./ai-harness.js',import.meta.url)),
  modulesRules:[{type:'ESModule',include:['**/*.js']}],compatibilityDate:'2026-07-30',
  d1Databases:{DB:'00000000-0000-0000-0000-000000000003'},bindings:{AI_SEARCH_ENABLED:'true'},
  outboundService:async request=>{
    calls.push(await request.json());if(hold)await hold;
    return Response.json({choices:[{message:{content:JSON.stringify(reply)}}]},{status:fail?503:200});
  }};
before(async()=>{
  mf=new Miniflare(settings);db=await mf.getD1Database('DB');
  for(const file of ['0001_accounts.sql','0002_credentials.sql','0003_ai_search.sql']){
    const sql=await readFile(new URL('../migrations/'+file,import.meta.url),'utf8');
    let statement='';
    for(const line of sql.split('\n')){
      if(line.trim().startsWith('--'))continue;
      statement+=line+'\n';
      if(line.trim().endsWith(';')&&(!statement.trim().startsWith('CREATE TRIGGER')||line.trim()==='END;')){
        await db.prepare(statement).run();statement='';
      }
    }
  }
});
after(async()=>{await mf?.dispose();});
beforeEach(async()=>{
  calls=[];hold=null;fail=false;reply={answer:'Кража автомобиля: смотрите [1].',references:[1]};
  await db.batch(['ai_answer_cache','ai_daily_usage','ai_global_usage','ai_documents','ai_catalog_state','accounts'].map(table=>db.prepare('DELETE FROM '+table)));
  await db.batch(['a','b'].map(id=>db.prepare('INSERT INTO accounts VALUES(?,?,?,0)').bind(id,id,'Example')));
  await db.prepare("INSERT INTO ai_catalog_state VALUES('active','revision1')").run();
  for(const [id,server,kind] of [['doc1','murrieta','laws'],['doc2','eclipse','laws'],['doc3','murrieta','rules']]){
    await db.prepare('INSERT INTO ai_documents VALUES(?,?,?,?,?,?,?,?,?,?)').bind('revision1',id,server,kind,'Кража автомобиля','Наказание: 2 года. Кража чужого автомобиля.', 'https://forum.gta5rp.com/threads/test/', 'УК','1.1','Уголовный').run();
  }
});
async function search(data={}){
  return mf.dispatchFetch('https://test/search',{method:'POST',body:JSON.stringify({account:'a',server:'murrieta',scope:'laws',query:'украл чужой автомобиль',...data})});
}
async function getQuota(account='a'){
  return (await (await mf.dispatchFetch('https://test/quota',{method:'POST',body:JSON.stringify({account})})).json()).quota;
}
test('answers use only the selected server and scope, repeat answers use no model or quota',async()=>{
  let result=await (await search()).json();
  assert.equal(result.cached,false);assert.equal(result.quota.remaining,4);
  assert.equal(result.sources[0].id,'doc1');assert.equal(calls.length,1);
  const context=JSON.parse(calls[0].input.messages[1].content);
  assert.equal(context.server,'murrieta');assert.equal(context.excerpts.length,1);
  result=await (await search({query:'  УКРАЛ   чужой автомобиль!!  '})).json();
  assert.equal(result.cached,true);assert.equal(result.quota.remaining,4);assert.equal(calls.length,1);
  assert.equal(result.charged,false);
});
test('limit is five new questions per account, cached answers still work at the limit',async()=>{
  for(let i=0;i<5;i++)assert.equal((await search({query:'кража автомобиля ситуация '+i})).status,200);
  assert.equal((await getQuota()).remaining,0);
  assert.equal((await search({query:'кража автомобиля шестой запрос'})).status,429);
  assert.equal((await (await search({query:'кража автомобиля ситуация 0'})).json()).cached,true);
  assert.equal((await getQuota('b')).remaining,5);
  assert.equal((await search({account:'b'})).status,200);
  assert.equal(calls.length,6);
});
test('parallel duplicate questions produce one generation; parallel different requests cannot exceed five',async()=>{
  let release;hold=new Promise(resolve=>{release=resolve;});
  const first=search();while(!calls.length)await new Promise(r=>setTimeout(r,5));
  assert.equal((await (await search()).json()).status,'pending');
  release();hold=null;assert.equal((await first).status,200);assert.equal(calls.length,1);
  const results=await Promise.all(Array.from({length:8},(_,i)=>search({query:'кража автомобиля параллельная '+i})));
  assert.equal(results.filter(r=>r.status===200).length,4);
  assert.equal((await getQuota()).used,5);assert.equal(calls.length,5);
});
test('model failures refund account quota and never cache an invalid or invented citation',async()=>{
  fail=true;assert.equal((await search()).status,503);assert.equal((await getQuota()).remaining,5);
  fail=false;reply.references=[99];assert.equal((await search()).status,503);assert.equal((await getQuota()).remaining,5);
  reply.references=[1];assert.equal((await search()).status,200);assert.equal((await getQuota()).remaining,4);
});
test('unknown subjects do not consume quota; client cannot inject account or model context',async()=>{
  assert.equal((await (await search({query:'электронный космолёт плазма'})).json()).charged,false);
  assert.equal(calls.length,0);assert.equal((await getQuota()).remaining,5);
  assert.equal((await search({account_id:'b'})).status,400);
  assert.equal((await search({context:'trust me'})).status,400);
});
test('cache and limits persist across restart; other catalog revisions cannot reuse stale answers',async()=>{
  await search();await mf.setOptions(settings);db=await mf.getD1Database('DB');
  assert.equal((await (await search()).json()).cached,true);assert.equal((await getQuota()).used,1);
  await db.prepare("UPDATE ai_catalog_state SET revision='revision2'").run();
  await db.prepare("UPDATE ai_documents SET revision='revision2'").run();
  assert.equal((await (await search()).json()).cached,false);assert.equal((await getQuota()).used,2);
});
test('only current UTC day counts and cached responses are private to the account',async()=>{
  await db.prepare("INSERT INTO ai_daily_usage VALUES('a','2000-01-01',5)").run();
  assert.equal((await getQuota()).remaining,5);
  await search();assert.equal((await (await search({account:'b'})).json()).cached,false);
  assert.equal(calls.length,2);
});
