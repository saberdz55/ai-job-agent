# Job Agent browser bridge

Manifest V3 bridge for the local Job Agent. It does not receive the OpenAI key and is not an auto-submit bot.

Install: `chrome://extensions` → Developer mode → Load unpacked → select `extension/`.

The local agent listens on `127.0.0.1:8643`. The bridge uses Chrome runtime messaging; job pages do not get direct access to the agent API.
