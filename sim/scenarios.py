"""The six test scenarios. Each lasts 900 s with its event in the middle."""

from dataclasses import dataclass
from typing import Dict, Optional


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

    def in_event(self, t: float) -> bool:
        return (self.event_start is not None
                and self.event_start <= t < self.event_end)


SCENARIOS: Dict[str, Scenario] = {s.key: s for s in (
    Scenario("normal", "1 Normal", "Open sea, healthy satellites.", "normal"),
    Scenario("interference", "2 Regular interference",
             "Multipath weakens some satellites and adds noise. Harmless: no hard alarm expected.",
             "interference", 300, 600),
    Scenario("jamming", "3 Jamming",
             "A jammer drowns all signals from 120 to 360 s.", "jamming", 120, 360),
    Scenario("crude_spoof", "4 Crude spoofing",
             "Twelve strong, identical fake satellites from one direction move the "
             "position 2.5 km (120-360 s).", "crude_spoof", 120, 360),
    Scenario("smart_spoof", "5 Smart spoofing",
             "Normal-looking signals slowly drag the position north at 1.2 m/s (120-420 s).",
             "smart_spoof", 120, 420),
    Scenario("lost", "6 Signal lost",
             "No satellites at all from 120 to 420 s (antenna or cable failure).",
             "lost", 120, 420),
    Scenario("lost_no_fixes", "6b Signal lost, no radar/depth fixes",
             "Same outage with radar and depth fixes switched off: the uncertainty "
             "circle keeps growing.", "lost", 120, 420, fixes_enabled=False),
)}
