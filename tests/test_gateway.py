from job_agent.agent_gateway import new_gateway_config, valid_origin

def test_gateway_token_is_random_and_nonempty():
    a = new_gateway_config(); b = new_gateway_config()
    assert a.token and b.token and a.token != b.token

def test_gateway_origin_allowlist():
    assert valid_origin(None)
    assert valid_origin("http://127.0.0.1:8643")
    assert valid_origin("http://localhost:8643")
    assert not valid_origin("https://evil.example")
