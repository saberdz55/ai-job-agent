from pathlib import Path


def test_extension_has_no_openai_key_and_no_submit_action():
    manifest = Path('extension/manifest.json').read_text(encoding='utf-8')
    bridge = Path('extension/agent-bridge.js').read_text(encoding='utf-8')
    worker = Path('extension/service-worker.js').read_text(encoding='utf-8')
    assert 'OPENAI_API_KEY' not in manifest + bridge + worker
    assert 'submit' not in bridge.lower()
    assert 'submit' not in worker.lower()


def test_server_refuses_non_local_bind_and_has_extension_route():
    source = Path('src/job_agent/agent_server.py').read_text(encoding='utf-8')
    assert 'Agent server refuses non-local bind' in source
    assert '@app.post("/api/agent/extension")' in source
    assert 'unsupported_extension_action' in source
