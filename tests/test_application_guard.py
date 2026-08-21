from job_agent.application_guard import classify_field, propose_field, validate_answer


def test_classifies_common_fields():
    assert classify_field("Email address", "email") == "email"
    assert classify_field("Years of experience") == "experience_years"
    assert classify_field("Visa sponsorship") == "sponsorship"


def test_missing_fact_never_becomes_a_value():
    proposal = propose_field("Phone", "phone", {})
    assert proposal.status == "UNKNOWN"
    assert proposal.value is None


def test_verified_fact_is_proposed():
    proposal = propose_field("Email address", "email", {"email": "a@example.com"})
    assert proposal.status == "VERIFIED"
    assert proposal.value == "a@example.com"


def test_sensitive_fields_always_require_review():
    proposal = propose_field("Visa sponsorship", "sponsorship", {"sponsorship": "no"})
    assert proposal.status == "REVIEW"
    assert proposal.value is None
    assert validate_answer("sponsorship", "no", {"sponsorship": "no"})[0] is False
    assert validate_answer("work_authorization", "yes", {"work_authorization": "yes"})[0] is False


def test_answer_validation_fails_closed():
    assert validate_answer("email", "a@example.com", {})[0] is False
    assert validate_answer("email", "a@example.com", {"email": "a@example.com"})[0] is True
