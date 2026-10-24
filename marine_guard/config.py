"""Every tunable number used by the guard, in one place.

Units: metres, seconds, metres per second, dB-Hz (signal strength C/N0)
and dB (receiver noise floor / AGC).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardConfig:
    # --- Where local metres are anchored on the globe ---------------------
    origin_lat_deg: float = 59.75
    """Latitude of local (0, 0): mid Gulf of Finland (degrees north)."""

    origin_lon_deg: float = 24.30
    """Longitude of local (0, 0) (degrees east)."""

    # --- GNSS receiver -------------------------------------------------
    gnss_noise: float = 2.0
    """Typical GNSS position noise per axis in open sky (m)."""

    min_sats: int = 5
    """Satellites we require. A fix needs 4 (3 position axes + clock);
    the 5th lets us check that the measurements agree with each other."""

    # --- Signal health checks -------------------------------------------
    agc_jump_db: float = 3.0
    """Noise floor rise above normal that means someone is jamming (dB)."""

    cn0_drop_db: float = 8.0
    """Drop of mean signal strength below normal that means jamming (dB-Hz)."""

    cn0_rise_db: float = 5.0
    """Rise of mean signal strength above normal that means a nearby
    transmitter is faking the satellites (dB-Hz)."""

    min_spread_db: float = 2.0
    """Real satellites differ in strength by about 4 dB-Hz; fakes from one
    transmitter look alike. A spread below this means spoofing (dB-Hz)."""

    time_tol_s: float = 0.1
    """Allowed change of the receiver clock offset from normal (s)."""

    # --- Position consistency ---------------------------------------------
    start_sigma: float = 3.0
    """Dead-reckoning uncertainty per axis right after a GNSS anchor (m)."""

    gate_k: float = 3.0
    """How many uncertainties apart GNSS and dead reckoning may be."""

    gate_floor_m: float = 10.0
    """Fixed extra allowance added to the position gate (m)."""

    degraded_gate_fraction: float = 0.5
    """Above this fraction of the gate the position is called DEGRADED."""

    depth_tol_fraction: float = 0.2
    """Allowed sounder-vs-chart mismatch as a fraction of measured depth."""

    depth_tol_m: float = 5.0
    """Fixed extra allowance for sounder-vs-chart mismatch (m)."""

    # --- Dead reckoning -----------------------------------------------------
    drift_per_speed: float = 0.02
    """Uncertainty growth per axis for each m/s of speed (m per s per m/s)."""

    drift_floor: float = 0.05
    """Uncertainty growth per axis even when stopped (m per s)."""

    anchor_every_s: float = 30.0
    """While trusted, re-anchor dead reckoning to GNSS this often (s)."""

    current_learn_gain: float = 0.5
    """Fraction of the observed drift taken into the sea-current estimate."""

    # --- Recovery -------------------------------------------------------------
    recover_hard_s: int = 60
    """Clean seconds needed after jamming, spoofing or signal loss."""

    recover_soft_s: int = 10
    """Clean seconds needed after a DEGRADED period."""

    blend_weight: float = 0.3
    """Share of GNSS in the output position while DEGRADED."""

    # --- Learning normal conditions -----------------------------------------
    baseline_learn_rate: float = 0.05
    """Exponential-average rate for the normal C/N0, noise floor and clock."""

    trusted_uncertainty: float = 5.0
    """Reported position uncertainty while GNSS is trusted (m)."""

    # --- Radar fix ---------------------------------------------------------------
    use_radar_fixes: bool = True
    """Switch radar range-to-coast fixes on or off."""

    radar_every_s: float = 10.0
    """Time between radar fixes while on backup (s)."""

    radar_sigma: float = 15.0
    """Radar range accuracy (m)."""

    coast_y: float = 3000.0
    """Fallback coast: a straight east-west line at this north coordinate (m),
    used only when the chart cannot tell where the coast north of us is."""

    radar_gate_k: float = 3.0
    """A radar fix is accepted only within this many sigmas ..."""

    radar_gate_floor_m: float = 40.0
    """... plus this fixed allowance (m)."""

    # --- Depth-profile fix ----------------------------------------------------
    use_depth_fixes: bool = True
    """Switch depth-profile matching fixes on or off."""

    depth_every_s: float = 30.0
    """Time between depth-profile matches while on backup (s)."""

    depth_window_s: int = 60
    """Number of one-second depth samples compared with the chart."""

    depth_min_range_m: float = 3.0
    """The seabed must vary at least this much in the window to be useful (m)."""

    depth_step_m: float = 5.0
    """Step of the east-west shift search (m)."""

    depth_min_reach_m: float = 30.0
    """Smallest east-west search distance (m)."""

    depth_max_reach_m: float = 400.0
    """Largest east-west search distance (m)."""

    depth_max_cost: float = 3.0
    """Best match is accepted only if its mean squared depth error is below
    this (m^2)."""

    depth_fix_sigma: float = 20.0
    """Accuracy of an accepted depth-profile fix (m)."""

    # --- Independent fixes from other aids (pseudolites, nearby ships) ----
    use_aux_fixes: bool = True
    """Use independent fixes (AuxFix) while GNSS is not trusted."""

    aux_gate_k: float = 3.0
    """An independent fix is accepted only within this many combined sigmas ..."""

    aux_gate_floor_m: float = 40.0
    """... plus this fixed allowance (m). Unencrypted fixes that pass the gate
    are trusted, so a slowly drifting fake can still lead the ship astray."""

    max_pseudolite_hdop: float = 5.0
    """Pseudolite fixes with worse station geometry than this are dropped."""
