import {readFile} from 'node:fs/promises';
export async function applySchema(db) {
  for(const file of ['0001_accounts.sql','0002_credentials.sql','0003_ai_search.sql']) {
    const sql=await readFile(new URL('../migrations/'+file,import.meta.url),'utf8');
    let statement='';
    for(const line of sql.split('\n')) {
      if(line.trim().startsWith('--'))continue;
      statement+=line+'\n';
      if(line.trim().endsWith(';')&&(!statement.trim().startsWith('CREATE TRIGGER')||line.trim()==='END;')) {
        await db.prepare(statement).run();statement='';
      }
    }
  }
}
