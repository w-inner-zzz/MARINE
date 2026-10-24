"""What the boat does in each guard state.

The steps for jamming and spoofing summarise published advice (the Swedish
Maritime Administration, and the Estonian/Finnish communication circulated as
IMO Circular Letter No. 5037 of 19 June 2025). Educational summary only, not
legal advice or an official procedure.
"""

from types import MappingProxyType
from typing import Mapping

from .types import Action, State

_WHY_BACKUP = (
    "A wrong position can lead to grounding, collision, or leaving the planned "
    "route and the traffic lanes. In the shallow, busy Baltic a few hundred "
    "metres can be the difference between deep water and rocks."
)

RULE_LOOKOUT = "COLREG Rule 5 - keep a proper look-out by sight, hearing and all available means."
RULE_SAFE_SPEED = "COLREG Rule 6 - proceed at a safe speed for the conditions."
RULE_RISK = "COLREG Rule 7 - use radar and all available means to judge the risk of collision."
RULE_ACTION = "COLREG Rule 8 - take early, positive action to avoid collision."
RULE_SOLAS = ("SOLAS Chapter V - safe navigation, and the navigation systems "
              "ships must carry and use.")
ALL_RULES = (RULE_LOOKOUT, RULE_SAFE_SPEED, RULE_RISK, RULE_ACTION, RULE_SOLAS)

_IDENTIFY = ("Identify which systems use GNSS: position, course and speed over ground, "
             "and time (ECDIS, AIS, autopilot track mode, radar overlays, GMDSS clocks).")
_CROSS_CHECK = ("Cross-check the position with radar overlaid on the chart and other "
                "non-GNSS methods (bearings, ranges, depth soundings).")
_CHARTS = "Navigate with paper or electronic charts, the gyrocompass and the log."
_SLOW = "Slow down and increase the look-out."
_PLOT = "Keep a manual position plot at regular intervals."
_OTHERS = ("Watch nearby vessels carefully: their AIS positions may also be wrong, "
           "so trust radar and your eyes over AIS.")
_VTS = "Contact VTS or the sea rescue centre (MRCC) if safety is in doubt."
_REPORT = ("Report the interference to the coastal authorities "
           "(in Finland: Traficom).")
_LOG = ("Log times, positions and raw receiver readings (signal strength, satellite "
        "count, noise floor) as evidence.")

_HARD_STEPS = (
    _IDENTIFY,
    _CROSS_CHECK,
    "If GNSS is compromised, steer manually and navigate visually and by radar.",
    "If gyro data is unavailable, use Head-Up radar and switch off heading-dependent functions.",
    _CHARTS,
    _SLOW,
    _PLOT,
    _OTHERS,
    _VTS,
    _REPORT,
    _LOG,
)

_BACKUP_INSTRUCTIONS = (
    "Navigate on dead reckoning, cross-checked with radar ranges and depth soundings.",
    "Hold the gyro heading; avoid course changes unless needed for safety.",
    "Post an extra lookout.",
    "Take a manual position fix (radar/visual) every 10 minutes and plot it.",
)

ACTIONS: Mapping[State, Action] = MappingProxyType({
    State.TRUSTED: Action(
        position_source="GNSS",
        autopilot_mode="Track: follow route",
        recommended_speed_kn="Normal service speed",
        lookout_level="Normal",
        crew_instructions=("Continue the passage as planned.",),
        alerts=(),
        why_it_matters=("All checks agree, so the satellite position can be used. Good "
                        "practice still cross-checks it now and then, because "
                        "interference can start at any moment."),
        steps=(
            "Follow the planned route on the track autopilot.",
            "Now and then compare the GNSS position with radar ranges and the chart.",
            "Keep the backup tools (radar, depth sounder, paper chart) ready.",
        ),
        rules=(RULE_LOOKOUT, RULE_SOLAS),
    ),
    State.DEGRADED: Action(
        position_source="Blend of GNSS and dead reckoning",
        autopilot_mode="Track, with doubled safety margin to hazards",
        recommended_speed_kn="Normal service speed",
        lookout_level="Normal, with radar cross-check",
        crew_instructions=(
            "Cross-check the position on radar.",
            "Log the event in the deck log.",
        ),
        alerts=("GNSS accuracy degraded",),
        why_it_matters=("GNSS still works but disagrees more than usual with dead "
                        "reckoning: it may be noisy (multipath, weak signals) or the "
                        "start of an attack. Extra margin keeps a small error harmless."),
        steps=(
            "Double the safety margin to shallows and other hazards.",
            _CROSS_CHECK,
            "Log the time, position and what the receiver shows.",
            "Be ready to switch to backup navigation if the situation gets worse.",
        ),
        rules=(RULE_LOOKOUT, RULE_RISK, RULE_SOLAS),
    ),
    State.JAMMING: Action(
        position_source="Dead reckoning + radar + depth",
        autopilot_mode="Heading hold (gyro)",
        recommended_speed_kn="About 8 kn",
        lookout_level="Extra lookout",
        crew_instructions=_BACKUP_INSTRUCTIONS + (
            "Report the interference to the coast authority.",
        ),
        alerts=("GNSS JAMMING detected", "Report interference"),
        why_it_matters=("Jamming drowns the satellite signals in noise: the receiver loses "
                        "satellites or gives a poor position. " + _WHY_BACKUP),
        steps=_HARD_STEPS,
        rules=ALL_RULES,
    ),
    State.LOST: Action(
        position_source="Dead reckoning + radar + depth",
        autopilot_mode="Heading hold (gyro)",
        recommended_speed_kn="About 8 kn",
        lookout_level="Extra lookout",
        crew_instructions=("Check the GNSS antenna and cables first.",)
        + _BACKUP_INSTRUCTIONS + ("Report the outage if it persists.",),
        alerts=("GNSS signal LOST",),
        why_it_matters=("The receiver has too few satellites for a checkable position. "
                        "This may be a fault on board or interference. " + _WHY_BACKUP),
        steps=("Check the GNSS antenna and cables first.",) + _HARD_STEPS,
        rules=ALL_RULES,
    ),
    State.SPOOFING: Action(
        position_source="Dead reckoning + radar + visual (GNSS ignored)",
        autopilot_mode="Heading hold (gyro)",
        recommended_speed_kn="6-8 kn",
        lookout_level="Extra lookout",
        crew_instructions=(
            "Ignore GNSS completely, including AIS and ECDIS positions derived from it.",
            "Avoid narrow channels and busy traffic lanes.",
            "Fix the position by radar and visual bearings.",
            "Alert the master.",
            "Record evidence: screenshots, receiver logs, times.",
            "Report the spoofing to the coast authority.",
        ),
        alerts=("GNSS SPOOFING detected", "Master to the bridge"),
        why_it_matters=("Spoofing feeds the receiver fake signals, so it shows a confident "
                        "but wrong position. A track autopilot would steer the ship to "
                        "'correct' an error that does not exist. " + _WHY_BACKUP),
        steps=(
            "Alert the master.",
            "Stop using GNSS for navigation; take the autopilot out of track mode.",
        ) + _HARD_STEPS + (
            "Avoid narrow channels and busy traffic lanes until the position is confirmed.",
        ),
        rules=ALL_RULES,
    ),
    State.RECOVERING: Action(
        position_source="Dead reckoning + radar + depth (GNSS being re-checked)",
        autopilot_mode="Heading hold (gyro)",
        recommended_speed_kn="About 8 kn",
        lookout_level="Extra lookout",
        crew_instructions=(
            "Stay on backup navigation until GNSS has been clean for 60 seconds.",
            "Keep plotting manual fixes.",
        ),
        alerts=("GNSS recovering - not yet trusted",),
        why_it_matters=("Signals look clean again, but interference often comes and goes. "
                        "Waiting for 60 clean seconds avoids switching back too early."),
        steps=(
            "Stay on backup navigation.",
            "Compare the returning GNSS position with your plotted position.",
            "Switch back to GNSS only when the guard shows TRUSTED.",
            _LOG,
        ),
        rules=ALL_RULES,
    ),
})
