"""Plain-language wording for the decision banner and the playbook."""

from typing import Optional

from marine_guard import CheckResult, GuardResult, State

STATE_MEANING = {
    State.TRUSTED: "the satellite position can be used.",
    State.DEGRADED: "GNSS is noisier than normal, so it is blended with dead reckoning.",
    State.RECOVERING: "signals look clean again, but GNSS must stay clean for a while "
                      "before it is trusted.",
    State.LOST: "too few satellites: the ship navigates without GNSS.",
    State.JAMMING: "someone is drowning the satellite signals in noise: the ship "
                   "navigates without GNSS.",
    State.SPOOFING: "the satellite position is fake: the ship ignores GNSS completely.",
}

DISCLAIMER = ("Educational summary, not legal advice or an official procedure. Follow your "
              "company safety management system and the instructions of the flag state and "
              "coastal authority.")

RULE_SOURCES = {"COLREG": "colreg", "SOLAS": "solas_v"}
"""Which source each rule prefix links to."""

PLAYBOOK_SOURCES = (
    ("sma", "Swedish Maritime Administration (as reported)"),
    ("imo5037", "IMO Circular Letter No. 5037 (Estonia and Finland)"),
    ("fi_ee_warning", "Finnish-Estonian warning"),
    ("traficom_boating", "Traficom advice for boaters"),
)
"""(source key, link text) behind the playbook steps."""


def deciding_check(res: GuardResult) -> Optional[CheckResult]:
    return next((c for c in res.checks if c.passed is False), None)


def what_is_happening(res: GuardResult) -> str:
    a = res.action
    base = f"{res.state.value}: {STATE_MEANING[res.state]}"
    if res.state == State.TRUSTED:
        return f"{base} Autopilot: {a.autopilot_mode}."
    if res.state == State.RECOVERING:
        return (f"{base} Clean for {res.clean_seconds} of {res.clean_needed} seconds; "
                f"position from {a.position_source}.")
    return f"{base} Position from {a.position_source}; autopilot {a.autopilot_mode}."


def why(res: GuardResult) -> str:
    failed = [c for c in res.checks if c.passed is False]
    skipped = sum(c.passed is None for c in res.checks)
    skipped_text = f" ({skipped} could not run)" if skipped else ""
    if not failed:
        return f"All checks that could run passed{skipped_text}. {res.reason}"
    names = ", ".join(c.name for c in failed)
    return (f"{len(failed)} of {len(res.checks)} checks failed ({names}){skipped_text}. "
            f"The first failure decides: {res.reason}")
