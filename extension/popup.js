async function command(action){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  const out=document.getElementById('out');
  out.textContent='Analyzing…';
  chrome.tabs.sendMessage(tab.id,{type:'JOB_AGENT_PAGE_ACTION',action},response=>{
    if(chrome.runtime.lastError){out.textContent='Bridge unavailable on this page.';return;}
    out.textContent=JSON.stringify(response||{ok:false},null,2);
  });
}
document.getElementById('inspect').onclick=()=>command('inspect_page');
document.getElementById('preview').onclick=()=>command('fill_preview');
