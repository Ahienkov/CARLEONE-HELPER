import { search, quota } from '../src/ai_search.js';
export default {async fetch(request, env) {
  const data=await request.json();
  const db=env.DB.withSession('first-primary');
  try {
    const value=new URL(request.url).pathname==='/quota'?{quota:await quota(db,data.account)}:
      await search(data,data.account,env,db,async (model,input)=>{
        const response=await fetch('https://model.test/run',{method:'POST',body:JSON.stringify({model,input})});
        if (!response.ok) throw new Error('model outage');
        return response.json();
      });
    return Response.json(value);
  } catch(error) {return Response.json({error:error.message,...error.details},{status:error.status||500});}
}};
