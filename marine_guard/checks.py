"""Health checks run on every GNSS epoch.

All checks are evaluated every second so the full picture can be shown.
The verdict is the FIRST failing check in the order of CHECK_ORDER.
"""

import math
import statistics
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

from .config import GuardConfig
from .types import Chart, CheckResult, GnssEpoch, Position

OK = "OK"
DEGRADED = "DEGRADED"
LOST = "LOST"
JAMMING = "JAMMING"
SPOOFING = "SPOOFING"


@dataclass(frozen=True)
class Baselines:
    """What 'normal' looks like, learned while GNSS is trusted."""

    cn0_dbhz: float
    agc_db: float
    clock_s: float


@dataclass(frozen=True)
class CheckContext:
    epoch: GnssEpoch
    baselines: Baselines
    dr_position: Position
    total_uncertainty: float
    depth_m: Optional[float]
    chart: Optional[Chart]
    config: GuardConfig

    @property
    def cn0_values(self) -> Tuple[float, ...]:
        return tuple(s.cn0_dbhz for s in self.epoch.tracked)

    @property
    def gap(self) -> Optional[float]:
        """Distance between the GNSS position and dead reckoning (m)."""
        if self.epoch.position is None:
            return None
        gx, gy = self.epoch.position
        dx, dy = self.dr_position
        return math.hypot(gx - dx, gy - dy)

    @property
    def gate(self) -> float:
        """Largest believable gap given the dead-reckoning uncertainty (m)."""
        cfg = self.config
        return cfg.gate_k * self.total_uncertainty + cfg.gate_floor_m


def _skipped(name: str, verdict: str, why: str) -> CheckResult:
    return CheckResult(name, None, None, None, f"Not checked: {why}.", verdict)


def check_noise_floor(ctx: CheckContext) -> CheckResult:
    rise = ctx.epoch.agc_db - ctx.baselines.agc_db
    limit = ctx.config.agc_jump_db
    return CheckResult(
        "Noise floor", rise <= limit, rise, limit,
        f"Noise floor {ctx.epoch.agc_db:.1f} dB is {rise:+.1f} dB from normal "
        f"{ctx.baselines.agc_db:.1f} dB (alarm above +{limit:.1f} dB).",
        JAMMING,
    )


def check_satellite_count(ctx: CheckContext) -> CheckResult:
    count = len(ctx.epoch.tracked)
    need = ctx.config.min_sats
    has_fix = ctx.epoch.position is not None
    passed = count >= need and has_fix
    fix_text = "" if has_fix else " and the receiver reports no position"
    return CheckResult(
        "Satellite count", passed, float(count), float(need),
        f"{count} satellites tracked (need {need}){fix_text}.",
        LOST,
    )


def check_cn0_drop(ctx: CheckContext) -> CheckResult:
    values = ctx.cn0_values
    if not values:
        return _skipped("Signal strength drop", JAMMING, "no satellites tracked")
    mean = statistics.fmean(values)
    drop = ctx.baselines.cn0_dbhz - mean
    limit = ctx.config.cn0_drop_db
    return CheckResult(
        "Signal strength drop", drop <= limit, drop, limit,
        f"Mean signal {mean:.1f} dB-Hz is {drop:.1f} dB below normal "
        f"{ctx.baselines.cn0_dbhz:.1f} dB-Hz (alarm above {limit:.1f} dB).",
        JAMMING,
    )


def check_cn0_spread(ctx: CheckContext) -> CheckResult:
    values = ctx.cn0_values
    if len(values) < 2:
        return _skipped("Signal spread", SPOOFING, "fewer than 2 satellites")
    spread = statistics.pstdev(values)
    limit = ctx.config.min_spread_db
    return CheckResult(
        "Signal spread", spread >= limit, spread, limit,
        f"Satellite strengths differ by {spread:.1f} dB-Hz (std-dev); real "
        f"satellites differ by about 4, alarm below {limit:.1f}.",
        SPOOFING,
    )


def check_cn0_rise(ctx: CheckContext) -> CheckResult:
    values = ctx.cn0_values
    if not values:
        return _skipped("Signal strength rise", SPOOFING, "no satellites tracked")
    mean = statistics.fmean(values)
    rise = mean - ctx.baselines.cn0_dbhz
    limit = ctx.config.cn0_rise_db
    return CheckResult(
        "Signal strength rise", rise <= limit, rise, limit,
        f"Mean signal {mean:.1f} dB-Hz is {rise:+.1f} dB from normal "
        f"{ctx.baselines.cn0_dbhz:.1f} dB-Hz (alarm above +{limit:.1f} dB).",
        SPOOFING,
    )


def check_clock(ctx: CheckContext) -> CheckResult:
    error = ctx.epoch.gnss_time_error_s
    if error is None:
        return _skipped("Clock consistency", SPOOFING, "no receiver time")
    jump = abs(error - ctx.baselines.clock_s)
    limit = ctx.config.time_tol_s
    return CheckResult(
        "Clock consistency", jump <= limit, jump, limit,
        f"Receiver clock offset {error:.3f} s differs {jump:.3f} s from normal "
        f"{ctx.baselines.clock_s:.3f} s (alarm above {limit:.2f} s).",
        SPOOFING,
    )


def check_position_jump(ctx: CheckContext) -> CheckResult:
    gap = ctx.gap
    if gap is None:
        return _skipped("Position vs dead reckoning", SPOOFING, "no GNSS position")
    gate = ctx.gate
    return CheckResult(
        "Position vs dead reckoning", gap <= gate, gap, gate,
        f"GNSS is {gap:.0f} m from dead reckoning; at most {gate:.0f} m is "
        f"believable ({ctx.config.gate_k:.0f} x {ctx.total_uncertainty:.0f} m "
        f"uncertainty + {ctx.config.gate_floor_m:.0f} m).",
        SPOOFING,
    )


def check_on_water(ctx: CheckContext) -> CheckResult:
    if ctx.epoch.position is None:
        return _skipped("Position on water", SPOOFING, "no GNSS position")
    if ctx.chart is None:
        return _skipped("Position on water", SPOOFING, "no chart")
    x, y = ctx.epoch.position
    on_water = ctx.chart.is_water(x, y)
    text = ("GNSS position is on water." if on_water
            else f"GNSS position ({x:.0f}, {y:.0f}) m is on land.")
    return CheckResult("Position on water", on_water, None, None, text, SPOOFING)


def check_depth(ctx: CheckContext) -> CheckResult:
    if ctx.epoch.position is None:
        return _skipped("Depth vs chart", SPOOFING, "no GNSS position")
    if ctx.chart is None or ctx.depth_m is None:
        return _skipped("Depth vs chart", SPOOFING, "no chart or depth sounder")
    cfg = ctx.config
    chart_depth = ctx.chart.depth_at(*ctx.epoch.position)
    mismatch = abs(ctx.depth_m - chart_depth)
    limit = cfg.depth_tol_fraction * ctx.depth_m + cfg.depth_tol_m
    return CheckResult(
        "Depth vs chart", mismatch <= limit, mismatch, limit,
        f"Sounder reads {ctx.depth_m:.1f} m, chart at the GNSS position says "
        f"{chart_depth:.1f} m: {mismatch:.1f} m apart (alarm above {limit:.1f} m).",
        SPOOFING,
    )


def check_position_agreement(ctx: CheckContext) -> CheckResult:
    gap = ctx.gap
    if gap is None:
        return _skipped("Position agreement", DEGRADED, "no GNSS position")
    limit = ctx.config.degraded_gate_fraction * ctx.gate
    if gap <= limit:
        text = (f"GNSS and dead reckoning agree within {gap:.1f} m "
                f"(caution above {limit:.1f} m).")
    else:
        text = (f"GNSS is {gap:.1f} m from dead reckoning, above the caution "
                f"limit of {limit:.1f} m: noisy but not impossible.")
    return CheckResult("Position agreement", gap <= limit, gap, limit, text, DEGRADED)


CHECK_ORDER: Tuple[Callable[[CheckContext], CheckResult], ...] = (
    check_noise_floor,
    check_satellite_count,
    check_cn0_drop,
    check_cn0_spread,
    check_cn0_rise,
    check_clock,
    check_position_jump,
    check_on_water,
    check_depth,
    check_position_agreement,
)


def run_checks(ctx: CheckContext) -> Tuple[CheckResult, ...]:
    return tuple(check(ctx) for check in CHECK_ORDER)


def first_failure(checks: Sequence[CheckResult]) -> Optional[CheckResult]:
    return next((c for c in checks if c.passed is False), None)


def verdict_of(checks: Sequence[CheckResult]) -> str:
    failed = first_failure(checks)
    return OK if failed is None else failed.verdict_if_failed
