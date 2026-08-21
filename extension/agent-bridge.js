(() => {
  function snapshot() {
    const fields = [...document.querySelectorAll('input,select,textarea')];
    const text = (document.body?.innerText || '').slice(0, 20000).toLowerCase();
    return {
      forms: document.forms.length,
      fields: fields.length,
      has_captcha: /captcha|recaptcha|hcaptcha/.test(text),
      login_detected: /sign in|log in|create account|password/.test(text),
      field_names: fields.slice(0, 100).map(el => ({name: el.name || '', type: el.type || el.tagName.toLowerCase(), label: el.labels?.[0]?.innerText || ''}))
    };
  }
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || msg.type !== 'JOB_AGENT_PAGE_ACTION') return;
    if (msg.action === 'inspect_page' || msg.action === 'fill_preview') {
      chrome.runtime.sendMessage({type:'JOB_AGENT_COMMAND',payload:{action:msg.action,tab:{url:location.href,title:document.title},page:snapshot()}}, response => sendResponse(response || {ok:false,error:'no_response'}));
      return true;
    }
    sendResponse({ok:false,error:'unsupported_action'});
  });
})();
