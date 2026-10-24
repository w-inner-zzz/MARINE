"""Plain-language texts for every health check, filled with the real numbers.

Each entry has:
  measured  - what we measured (may use {value} and {threshold})
  means_ok  - what a pass means
  means_bad - what a fail means
  if_fails  - what a failure suggests
"""

from typing import Dict

from marine_guard import CheckResult

CHECK_EXPLANATIONS: Dict[str, Dict[str, str]] = {
    "Noise floor": {
        "measured": "The background radio noise is {value:+.1f} dB compared with its learned "
                    "normal level. The alarm is above +{threshold:.1f} dB.",
        "means_ok": "The receiver hears its usual background hiss: nobody is shouting on the "
                    "GNSS frequency.",
        "means_bad": "The background is far louder than normal: a transmitter nearby is "
                     "drowning the satellites.",
        "if_fails": "Suggests JAMMING. Satellites usually fade out next.",
    },
    "Satellite count": {
        "measured": "{value:.0f} satellites are tracked. We need at least {threshold:.0f}: "
                    "4 to compute a position and 1 extra to cross-check it.",
        "means_ok": "Enough satellites to compute a position and check that it is "
                    "consistent.",
        "means_bad": "Too few satellites for a position we can check.",
        "if_fails": "Suggests the signal is LOST: antenna or cable fault, a blocked view, or "
                    "interference strong enough to knock satellites out.",
    },
    "Signal strength drop": {
        "measured": "The average satellite's loudness fell by {value:.1f} dB compared with "
                    "normal (a negative number means it got louder). The alarm is a fall of "
                    "more than {threshold:.1f} dB.",
        "means_ok": "The satellites are about as loud as usual.",
        "means_bad": "All satellites have become much quieter at once, as if noise were "
                     "covering them.",
        "if_fails": "Suggests JAMMING (or a damaged antenna).",
    },
    "Signal spread": {
        "measured": "The satellites' loudness differs by {value:.1f} dB-Hz (standard "
                    "deviation). The alarm is below {threshold:.1f}.",
        "means_ok": "The satellites differ from each other, as real ones do: high "
                    "satellites are louder than low ones.",
        "means_bad": "The satellites are suspiciously alike, as if they all came from one "
                     "transmitter.",
        "if_fails": "Suggests SPOOFING: one fake transmitter imitating many satellites.",
    },
    "Signal strength rise": {
        "measured": "The average satellite is {value:+.1f} dB louder than normal. The alarm "
                    "is above +{threshold:.1f} dB.",
        "means_ok": "No satellite is louder than real satellites can be.",
        "means_bad": "The signals are louder than real satellites 20,000 km away can be.",
        "if_fails": "Suggests SPOOFING by a nearby transmitter.",
    },
    "Clock consistency": {
        "measured": "The receiver's clock offset moved {value:.3f} s from its normal value. "
                    "The alarm is above {threshold:.2f} s.",
        "means_ok": "The receiver's time agrees with what it has seen before.",
        "means_bad": "The receiver's time suddenly jumped.",
        "if_fails": "Suggests SPOOFING: fake signals often carry slightly wrong time.",
    },
    "Position vs dead reckoning": {
        "measured": "GNSS is {value:.0f} m from where dead reckoning says we are. At most "
                    "{threshold:.0f} m is believable.",
        "means_ok": "The GNSS position is where the ship could physically be.",
        "means_bad": "The GNSS position is further away than the ship could have drifted.",
        "if_fails": "Suggests SPOOFING: the position has been moved.",
    },
    "Position on water": {
        "measured": "We asked the chart whether the GNSS position is on water.",
        "means_ok": "The GNSS position is at sea, as it should be.",
        "means_bad": "The GNSS position is on land, where a ship cannot be.",
        "if_fails": "Suggests SPOOFING.",
    },
    "Depth vs chart": {
        "measured": "The depth sounder and the chart (at the GNSS position) differ by "
                    "{value:.1f} m. The alarm is above {threshold:.1f} m.",
        "means_ok": "The water under the keel is as deep as the chart says it should be "
                    "at the GNSS position.",
        "means_bad": "The water under the keel does not match the chart at the GNSS "
                     "position: we are probably somewhere else.",
        "if_fails": "Suggests SPOOFING.",
    },
    "Position agreement": {
        "measured": "GNSS is {value:.1f} m from dead reckoning. The caution limit (half the "
                    "believable distance) is {threshold:.1f} m.",
        "means_ok": "GNSS and dead reckoning agree closely.",
        "means_bad": "GNSS is noisier than usual but still possible.",
        "if_fails": "Suggests DEGRADED: multipath or weak signals, or the start of a slow "
                    "spoof. We blend GNSS with dead reckoning.",
    },
}

SKIPPED_MEANING = ("This check could not run this second (no data to compare), so it "
                   "neither passes nor fails.")


def explain(check: CheckResult) -> Dict[str, str]:
    """The three card texts for a check, filled with its real numbers."""
    texts = CHECK_EXPLANATIONS[check.name]
    if check.passed is None:
        return {"measured": check.text, "means": SKIPPED_MEANING, "if_fails": texts["if_fails"]}
    measured = texts["measured"]
    if check.value is not None and check.threshold is not None:
        measured = measured.format(value=check.value, threshold=check.threshold)
    return {
        "measured": measured,
        "means": texts["means_ok"] if check.passed else texts["means_bad"],
        "if_fails": texts["if_fails"],
    }
