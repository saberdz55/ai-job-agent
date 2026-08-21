"""Deterministic auto-apply entrypoint for one already-qualified job.

The discovery/matching agent decides which jobs qualify. This module executes one
application at a time. It may submit automatically only when AUTO_APPLY_ENABLED
and all existing application gates pass. It never bypasses CAPTCHA, login/2FA,
rate limits, or unresolved sensitive/legal fields.
"""
from __future__ import annotations

import os
from dataclasses import replace

from job_agent.apply.runner import ApplyConfig, run_apply


def auto_apply_enabled() -> bool:
    return os.environ.get("JOB_AGENT_AUTO_APPLY", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def run_auto_apply(config: ApplyConfig):
    """Run one application in autonomous mode.

    This does not weaken field validation. It only supplies the two execution
    locks already required by submit.py: an approval decision and submit mode.
    Blockers or unresolved required fields still stop the run.
    """
    if not auto_apply_enabled():
        raise RuntimeError(
            "JOB_AGENT_AUTO_APPLY is disabled. Set it explicitly to true before enabling auto-submit."
        )
    autonomous = replace(config, submit_flag=True, auto_approve=True)
    return run_apply(autonomous)
