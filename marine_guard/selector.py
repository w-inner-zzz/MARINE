"""Automatic choice of correction method: which independent position fixes
to trust, depending on the problem the guard has diagnosed.

Each method fails in different situations, so the choice follows the problem:

  TRUSTED     GNSS. Aids stay on standby.
  DEGRADED    GNSS blended with dead reckoning (the guard ignores aids here).
  LOST        pseudolites, nearby ships, seabed. Often our own receiver has
              failed, so nearby ships' GNSS is probably fine.
  JAMMING     pseudolites, seabed. Nearby ships share the jammed area.
  SPOOFING    pseudolites, seabed. Nearby ships may broadcast the same fake
              positions (their broadcasts are not encrypted).
  RECOVERING  the same as for the alarm that caused it.

All trusted methods that offer a fix are used (each fix still has to pass the
guard's plausibility gate); the first one in the list is the main method. If
none is available, the ship navigates on dead reckoning with the guard's
built-in radar and depth fixes. A method whose fixes the guard keeps rejecting
(REJECT_LIMIT offers in a row) is dropped for BAN_S seconds: its fixes
disagree with everything else we know.
"""

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

from .types import AuxFix, State

GNSS = "gnss"
BLEND = "blend"
DEAD_RECKONING = "dead_reckoning"
PSEUDOLITES = "pseudolites"
PEERS = "peers"
SEABED = "seabed"

TRUSTED_AIDS: Dict[State, Tuple[str, ...]] = {
    State.LOST: (PSEUDOLITES, PEERS, SEABED),
    State.JAMMING: (PSEUDOLITES, SEABED),
    State.SPOOFING: (PSEUDOLITES, SEABED),
}

WHY = {
    State.TRUSTED: "All checks pass: GNSS is used; the aids are on standby.",
    State.DEGRADED: "GNSS is noisier than usual: it is blended with dead reckoning.",
    State.LOST: ("Signal lost, often our own receiver: shore stations first, then nearby "
                 "ships (their GNSS is probably fine), then the seabed."),
    State.JAMMING: ("Jamming: nearby ships are probably jammed too, so they are not used; "
                    "shore stations and the seabed are."),
    State.SPOOFING: ("Spoofing: nearby ships may broadcast the same fake positions, so they "
                     "are not used; shore stations and the seabed cannot be faked this way."),
}
NONE_AVAILABLE = " None of them is available now: dead reckoning with radar and depth fixes."

REJECT_LIMIT = 30   # rejected offers in a row before a method is dropped
BAN_S = 300.0       # how long a dropped method stays out (s)
HOLD_S = 120.0      # a method counts as in use this long after its last offer (s)


def method_of(source: str) -> str:
    """Which method an AuxFix source belongs to ("peer:2" -> "peers")."""
    if source.startswith("peer"):
        return PEERS
    return {"pseudolite": PSEUDOLITES, "seabed": SEABED}.get(source, source)


@dataclass(frozen=True)
class Selection:
    methods: Tuple[str, ...]
    """Methods in use, main one first, e.g. ("pseudolites", "seabed") or ("gnss",)."""
    fixes: Tuple[AuxFix, ...]
    """The fixes to hand to the guard this second."""
    reason: str


class AidSelector:
    def __init__(self) -> None:
        self._last_alarm: Optional[State] = None
        self._last_offered: Tuple[str, ...] = ()
        self._reject_streak: Dict[str, int] = {}
        self._banned_until: Dict[str, float] = {}
        self._last_offer_t: Dict[str, float] = {}

    def choose(self, now: float, state: State, offers: Mapping[str, Sequence[AuxFix]],
               accepted_sources: Sequence[str]) -> Selection:
        """state: the guard's latest state; offers: fixes offered this second by
        each method; accepted_sources: what the guard accepted last second."""
        self._track_rejections(now, accepted_sources)

        if state in (State.LOST, State.JAMMING, State.SPOOFING):
            self._last_alarm = state
        problem = self._last_alarm if state == State.RECOVERING else state
        if problem == State.TRUSTED or problem is None:
            self._last_offered = ()
            return Selection((GNSS,), (), WHY[State.TRUSTED])
        if problem == State.DEGRADED:
            self._last_offered = ()
            return Selection((BLEND,), (), WHY[State.DEGRADED])

        trusted = [m for m in TRUSTED_AIDS[problem] if self._banned_until.get(m, -1.0) <= now]
        fixes, offered = [], []
        for method in trusted:
            if offers.get(method):
                fixes.extend(offers[method])
                offered.append(method)
                self._last_offer_t[method] = now
        self._last_offered = tuple(offered)

        in_use = tuple(m for m in trusted if now - self._last_offer_t.get(m, -1e9) <= HOLD_S)
        reason = WHY[problem]
        dropped = [m for m in TRUSTED_AIDS[problem] if m not in trusted]
        if dropped:
            reason += f" Dropped for now ({', '.join(dropped)}): its fixes disagree with our track."
        if not in_use:
            return Selection((DEAD_RECKONING,), tuple(fixes), reason + NONE_AVAILABLE)
        return Selection(in_use, tuple(fixes), reason)

    def _track_rejections(self, now: float, accepted_sources: Sequence[str]) -> None:
        accepted = {method_of(s) for s in accepted_sources}
        for method in self._last_offered:
            if method in accepted:
                self._reject_streak[method] = 0
                continue
            self._reject_streak[method] = self._reject_streak.get(method, 0) + 1
            if self._reject_streak[method] >= REJECT_LIMIT:
                self._banned_until[method] = now + BAN_S
                self._reject_streak[method] = 0
