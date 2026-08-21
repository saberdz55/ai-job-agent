from job_agent.browser_worker import inspect_html


def test_browser_inspection_blocks_captcha():
    result = inspect_html('<form><input name="email"></form><div>reCAPTCHA</div>')
    assert result.blocked is True
    assert result.has_captcha is True


def test_browser_inspection_detects_login():
    result = inspect_html('<form><input type="password"></form>Sign in')
    assert result.blocked is True
    assert result.login_detected is True


def test_browser_inspection_allows_normal_form():
    result = inspect_html('<form><input name="email"><input name="phone"></form>')
    assert result.blocked is False
    assert result.fields == 2
