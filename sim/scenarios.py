"""The scenarios.

SCENARIOS: six short test runs of 900 s (used by the tests).
VOYAGE_SCENARIOS: the same six as a 3-hour Baltic voyage in the Gulf of
Finland, with the event from 60 to 100 minutes.
"""

from dataclasses import dataclass, replace
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    description: str
    kind: str
    """normal | interference | jamming | crude_spoof | smart_spoof | lost"""
    event_start: Optional[float] = None
    event_end: Optional[float] = None
    fixes_enabled: bool = True
    duration: int = 900
    spoof_offset_m: Tuple[float, float] = (1500.0, 2000.0)
    """Crude spoofing: how far the fake position is shifted (east, north)."""

    @property
    def event_text(self) -> str:
        if self.event_start is None:
            return "no event"
        if self.duration > 3600:
            return f"event {self.event_start / 60:.0f}-{self.event_end / 60:.0f} min"
        return f"event {self.event_start:.0f}-{self.event_end:.0f} s"

    def in_event(self, t: float) -> bool:
        return (self.event_start is not None
                and self.event_start <= t < self.event_end)


SCENARIOS: Dict[str, Scenario] = {s.key: s for s in (
    Scenario("normal", "1 Normal", "Open sea, healthy satellites.", "normal"),
    Scenario("interference", "2 Regular interference",
             "Multipath weakens some satellites and adds noise. Harmless: no hard alarm expected.",
             "interference", 300, 600),
    Scenario("jamming", "3 Jamming",
             "A jammer drowns all signals.", "jamming", 120, 360),
    Scenario("crude_spoof", "4 Crude spoofing",
             "Twelve strong, identical fake satellites from one direction move the "
             "reported position 2.5 km.", "crude_spoof", 120, 360),
    Scenario("smart_spoof", "5 Smart spoofing",
             "Normal-looking signals slowly drag the reported position north at 1.2 m/s.",
             "smart_spoof", 120, 420),
    Scenario("lost", "6 Signal lost",
             "No satellites at all (antenna or cable failure).",
             "lost", 120, 420),
    Scenario("lost_no_fixes", "6b Signal lost, no radar/depth fixes",
             "Same outage with radar and depth fixes switched off: the uncertainty "
             "circle keeps growing.", "lost", 120, 420, fixes_enabled=False),
)}


VOYAGE_DURATION_S = 3 * 3600
VOYAGE_EVENT = (60 * 60.0, 100 * 60.0)
VOYAGE_SPOOF_OFFSET_M = (-8000.0, 44000.0)  # puts the fake track on the Finnish shore


def _voyage(sc: Scenario) -> Scenario:
    event = (None, None) if sc.event_start is None else VOYAGE_EVENT
    description = sc.description
    if sc.kind == "crude_spoof":
        description = ("Twelve strong, identical fake satellites from one direction put "
                       "the reported position on land about 45 km away.")
    return replace(sc, duration=VOYAGE_DURATION_S, event_start=event[0], event_end=event[1],
                   description=description, spoof_offset_m=VOYAGE_SPOOF_OFFSET_M)


VOYAGE_SCENARIOS: Dict[str, Scenario] = {k: _voyage(sc) for k, sc in SCENARIOS.items()}
