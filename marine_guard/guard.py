"""The GNSS trust monitor: one call per second decides whether the satellite
position can be trusted and, if not, navigates on backup sensors."""

import statistics
from typing import Optional, Sequence, Tuple

from . import checks as chk
from .actions import ACTIONS
from .backup import DeadReckoner
from .config import GuardConfig
from .geometry import LocalFrame
from .geometry import hdop as compute_hdop
from .types import (BACKUP_STATES, HARD_STATES, AuxFix, Chart, CheckResult, GnssEpoch,
                    GuardResult, Position, ShipSensors, State)


class GnssGuard:
    """Call update() once per GNSS epoch (normally every second)."""

    def __init__(self, chart: Optional[Chart] = None,
                 config: Optional[GuardConfig] = None):
        self.config = config or GuardConfig()
        self.chart = chart
        self.frame = LocalFrame(self.config.origin_lat_deg, self.config.origin_lon_deg)
        self.state = State.TRUSTED
        self._dr: Optional[DeadReckoner] = None
        self._baselines: Optional[chk.Baselines] = None
        self._last_time = 0.0
        self._anchor_time = 0.0
        self._last_radar_time = 0.0
        self._last_depth_time = 0.0
        self._clean_streak = 0
        self._clean_needed = 0

    # ------------------------------------------------------------------ API

    def update(self, epoch: GnssEpoch, sensors: ShipSensors,
               aux_fixes: Sequence[AuxFix] = ()) -> GuardResult:
        """aux_fixes: optional independent position fixes (pseudolites, nearby
        ships...). They never change the health checks; while GNSS is not
        trusted, plausible ones correct the dead reckoning."""
        now = epoch.timestamp
        if self._dr is None:
            self._start(epoch)
        dt = max(0.0, now - self._last_time)
        self._last_time = now

        # 1. Dead reckoning runs in every state.
        self._dr.step(sensors.heading_deg, sensors.speed_through_water_mps, dt,
                      sensors.depth_m)

        # 2. Health checks.
        hdop = epoch.hdop if epoch.hdop is not None else compute_hdop(epoch.satellites)
        ctx = chk.CheckContext(
            epoch=epoch,
            baselines=self._baselines,
            dr_position=self._dr.position,
            total_uncertainty=self._dr.total_uncertainty,
            depth_m=sensors.depth_m,
            chart=self.chart,
            config=self.config,
        )
        results = chk.run_checks(ctx)
        verdict = chk.verdict_of(results)

        # 3. State machine.
        became_trusted = self._advance_state(verdict, epoch)

        # 4. Output and side effects of the new state.
        position, uncertainty, fixes, aux_used = self._apply_state(epoch, sensors, ctx, aux_fixes)
        lat, lon = self.frame.to_latlon(*position)
        gnss_lat = gnss_lon = None
        if epoch.position is not None:
            gnss_lat, gnss_lon = self.frame.to_latlon(*epoch.position)

        return GuardResult(
            timestamp=now,
            state=self.state,
            position=position,
            uncertainty_m=uncertainty,
            reason=self._reason(verdict, results, ctx, became_trusted),
            checks=results,
            hdop=hdop,
            satellite_count=len(epoch.tracked),
            action=ACTIONS[self.state],
            verdict=verdict,
            clean_seconds=self._clean_streak,
            clean_needed=self._clean_needed,
            fixes=fixes,
            aux_used=aux_used,
            lat_deg=lat,
            lon_deg=lon,
            gnss_position=epoch.position,
            gnss_lat_deg=gnss_lat,
            gnss_lon_deg=gnss_lon,
            baseline_cn0_dbhz=ctx.baselines.cn0_dbhz,
            baseline_agc_db=ctx.baselines.agc_db,
            baseline_clock_s=ctx.baselines.clock_s,
        )

    # ------------------------------------------------------------ internals

    def _start(self, epoch: GnssEpoch) -> None:
        """Trust the first epoch and take 'normal' from it."""
        start = epoch.position if epoch.position is not None else (0.0, 0.0)
        self._dr = DeadReckoner(start, self.config)
        cn0 = [s.cn0_dbhz for s in epoch.tracked]
        self._baselines = chk.Baselines(
            cn0_dbhz=statistics.fmean(cn0) if cn0 else 0.0,
            agc_db=epoch.agc_db,
            clock_s=epoch.gnss_time_error_s or 0.0,
        )
        self._last_time = self._anchor_time = epoch.timestamp

    def _advance_state(self, verdict: str, epoch: GnssEpoch) -> bool:
        """Apply the verdict. Returns True if GNSS became trusted again."""
        cfg = self.config
        if verdict in (chk.LOST, chk.JAMMING, chk.SPOOFING):
            if self.state not in BACKUP_STATES:
                self._last_radar_time = self._last_depth_time = epoch.timestamp
            self.state = State(verdict)
            self._clean_streak = 0
            self._clean_needed = cfg.recover_hard_s
        elif verdict == chk.DEGRADED:
            if self.state == State.TRUSTED:
                self.state = State.DEGRADED
                self._clean_streak = 0
                self._clean_needed = cfg.recover_soft_s
            elif self.state == State.DEGRADED:
                self._clean_streak = 0
            # On backup the streak pauses: it neither counts nor resets.
        elif self.state != State.TRUSTED:
            self._clean_streak += 1
            if self._clean_streak >= self._clean_needed:
                self.state = State.TRUSTED
                self._dr.anchor_to(epoch.position)
                self._anchor_time = epoch.timestamp
                return True
            if self.state in HARD_STATES:
                self.state = State.RECOVERING
        return False

    def _apply_state(self, epoch: GnssEpoch, sensors: ShipSensors, ctx: chk.CheckContext,
                     aux_fixes: Sequence[AuxFix]
                     ) -> Tuple[Position, float, Tuple[str, ...], Tuple[str, ...]]:
        dr = self._dr
        if self.state == State.TRUSTED:
            self._learn(epoch)
            return epoch.position, self.config.trusted_uncertainty, (), ()

        if self.state == State.DEGRADED:
            w = self.config.blend_weight
            (gx, gy), (dx, dy) = epoch.position, dr.position
            blended = (dx + w * (gx - dx), dy + w * (gy - dy))
            return blended, max(dr.total_uncertainty, ctx.gap), (), ()

        fixes = self._backup_fixes(epoch.timestamp, sensors)
        aux_used = self._aux_fixes(aux_fixes)
        return dr.position, dr.total_uncertainty, fixes, aux_used

    def _learn(self, epoch: GnssEpoch) -> None:
        """Only while trusted: track slow changes of 'normal' and the current."""
        rate = self.config.baseline_learn_rate
        base = self._baselines
        cn0 = [s.cn0_dbhz for s in epoch.tracked]
        clock = epoch.gnss_time_error_s
        self._baselines = chk.Baselines(
            cn0_dbhz=base.cn0_dbhz + rate * (statistics.fmean(cn0) - base.cn0_dbhz),
            agc_db=base.agc_db + rate * (epoch.agc_db - base.agc_db),
            clock_s=base.clock_s if clock is None
            else base.clock_s + rate * (clock - base.clock_s),
        )

        since_anchor = epoch.timestamp - self._anchor_time
        if since_anchor >= self.config.anchor_every_s:
            self._dr.learn_current(epoch.position, since_anchor)
            self._dr.anchor_to(epoch.position)
            self._anchor_time = epoch.timestamp

    def _backup_fixes(self, now: float, sensors: ShipSensors) -> Tuple[str, ...]:
        cfg = self.config
        fixes = []
        if cfg.use_radar_fixes and now - self._last_radar_time >= cfg.radar_every_s:
            self._last_radar_time = now
            coast_y = self._coast_y_north_of_estimate()
            if (sensors.radar_range_to_coast_m is not None and coast_y is not None
                    and self._dr.radar_fix(sensors.radar_range_to_coast_m, coast_y)):
                fixes.append("radar")
        if cfg.use_depth_fixes and now - self._last_depth_time >= cfg.depth_every_s:
            self._last_depth_time = now
            if self.chart is not None and self._dr.depth_fix(self.chart):
                fixes.append("depth")
        return tuple(fixes)

    def _aux_fixes(self, aux_fixes: Sequence[AuxFix]) -> Tuple[str, ...]:
        if not self.config.use_aux_fixes:
            return ()
        return tuple(f.source for f in aux_fixes
                     if self._dr.aux_fix(f.position, f.sigma_m, f.sigma_north))

    def _coast_y_north_of_estimate(self) -> Optional[float]:
        coast_y_at = getattr(self.chart, "coast_y_at", None)
        if coast_y_at is None:
            return self.config.coast_y
        return coast_y_at(self._dr.x, self._dr.y)

    def _reason(self, verdict: str, results: Tuple[CheckResult, ...],
                ctx: chk.CheckContext, became_trusted: bool) -> str:
        failed = chk.first_failure(results)
        clean = f"clean for {self._clean_streak}/{self._clean_needed} s"

        if self.state == State.TRUSTED:
            sats = len(ctx.epoch.tracked)
            if became_trusted:
                return (f"GNSS has been {clean}: trusted again with {sats} "
                        f"satellites, {ctx.gap:.1f} m from dead reckoning.")
            return (f"All checks passed: {sats} satellites, GNSS within "
                    f"{ctx.gap:.1f} m of dead reckoning.")
        if failed is None:
            return f"All checks pass again; {clean} before GNSS is trusted."
        if self.state in BACKUP_STATES and verdict == chk.DEGRADED:
            return f"Recovery paused ({clean}): {failed.text}"
        return failed.text
