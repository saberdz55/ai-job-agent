from __future__ import annotations

from pathlib import Path

import pytest


def test_phone_module_imports_without_playwright():
    # Importing phone mode must not import Playwright. This is the key Android
    # regression guard: Pydroid should be able to start the backend even when
    # desktop browser binaries are unavailable.
    import job_agent.phone as phone

    assert callable(phone.main)
    assert callable(phone._phone_app)


def test_phone_rejects_non_local_bind():
    from job_agent.phone import main

    with pytest.raises(SystemExit, match="Refusing non-local bind"):
        main(["--host", "0.0.0.0", "--no-open"])
