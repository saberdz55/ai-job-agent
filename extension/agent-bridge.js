(() => {
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || msg.type !== "JOB_AGENT_COMMAND") return;
    if (!msg.payload || typeof msg.payload !== "object") { sendResponse({ok:false,error:"invalid_payload"}); return; }
    chrome.runtime.sendMessage(msg, (response) => sendResponse(response || {ok:false,error:"no_response"}));
    return true;
  });
})();
