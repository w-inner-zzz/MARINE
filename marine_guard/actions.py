"""What the boat does in each guard state."""

from types import MappingProxyType
from typing import Mapping

from .types import Action, State

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
    ),
    State.LOST: Action(
        position_source="Dead reckoning + radar + depth",
        autopilot_mode="Heading hold (gyro)",
        recommended_speed_kn="About 8 kn",
        lookout_level="Extra lookout",
        crew_instructions=("Check the GNSS antenna and cables first.",)
        + _BACKUP_INSTRUCTIONS + ("Report the outage if it persists.",),
        alerts=("GNSS signal LOST",),
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
    ),
})
