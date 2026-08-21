const PORT=8643;
const API=`http://127.0.0.1:${PORT}`;
chrome.runtime.onMessage.addListener((msg,sender,sendResponse)=>{
  if(!msg||msg.type!=="JOB_AGENT_COMMAND") return;
  const payload=msg.payload||{};
  fetch(`${API}/api/agent/extension`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...payload,tab:{id:sender.tab?.id??null,url:sender.tab?.url??null,title:sender.tab?.title??null}})})
   .then(async r=>sendResponse({ok:r.ok,data:await r.json().catch(()=>({}))}))
   .catch(()=>sendResponse({ok:false,error:"gateway_unavailable"}));
  return true;
});
