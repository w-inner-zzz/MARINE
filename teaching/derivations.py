"""'Derivations' tab: the maths behind each step, no skipped steps, every symbol
defined, each with a worked number example. Kept separate so the text is easy
to edit."""

import math
import statistics
from typing import List, Optional, Tuple


from marine_guard import GuardConfig

from .blocks import Blocks
from marine_guard.geometry import geometry_row, invert_4x4
from sim.runner import Row

C_LIGHT = 299_792_458.0


def _matrix_latex(m, fmt="{:.2f}") -> str:
    rows = [" & ".join(fmt.format(v) for v in row) for row in m]
    return r"\begin{pmatrix}" + r" \\ ".join(rows) + r"\end{pmatrix}"


def position_from_satellites(row: Optional[Row]) -> Blocks:
    out = Blocks()
    out.md("""
**Symbols.** $\\mathbf r = (x, y, z)$ is the receiver position we want, $\\mathbf s_i$ the
known position of satellite $i$, $c$ the speed of light, $\\delta t$ the receiver clock
error (seconds), $e_i$ the measurement noise, and $\\rho_i$ the **pseudorange**: the
distance the receiver *thinks* it measured to satellite $i$.

**Step 1: what is measured.** The travel time times $c$ gives a distance that includes the
clock error:""")
    out.latex(r"\rho_i = \lVert \mathbf s_i - \mathbf r \rVert + c\,\delta t + e_i")
    out.md(f"""
*Example:* a clock error of $\\delta t = 1\\,\\mu s$ adds $c\\,\\delta t =
{C_LIGHT:,.0f} \\times 10^{{-6}} \\approx 300$ m to **every** pseudorange.

**Step 2: linearise.** The distance is not linear in $\\mathbf r$, so start from a guess
$\\mathbf r_0$ (say, the last position) and write $\\mathbf r = \\mathbf r_0 + \\Delta\\mathbf r$.
A first-order Taylor expansion of the distance gives""")
    out.latex(r"\lVert \mathbf s_i - \mathbf r \rVert \approx \lVert \mathbf s_i - \mathbf r_0"
             r" \rVert - \mathbf u_i \cdot \Delta \mathbf r, \qquad \mathbf u_i = "
             r"\frac{\mathbf s_i - \mathbf r_0}{\lVert \mathbf s_i - \mathbf r_0 \rVert}")
    out.md("""
where $\\mathbf u_i$ is the unit vector from the receiver to satellite $i$. Moving
*towards* a satellite shortens the distance, hence the minus sign.

**Step 3: one equation per satellite.** Let $d_i = \\rho_i - \\lVert \\mathbf s_i - \\mathbf r_0
\\rVert$ be the measured-minus-predicted range and $b = c\\,\\delta t$ the clock term in
metres. Then""")
    out.latex(r"d_i = -\mathbf u_i \cdot \Delta\mathbf r + b + e_i")
    out.md("""
With azimuth $az_i$ and elevation $el_i$, the unit vector in (east, north, up) is
$(\\cos el\\,\\sin az,\\ \\cos el\\,\\cos az,\\ \\sin el)$, so each satellite gives one row of
the **geometry matrix** $G$:""")
    out.latex(r"G_i = \begin{pmatrix} -\cos el_i \sin az_i & -\cos el_i \cos az_i & -\sin el_i"
             r" & 1 \end{pmatrix}, \qquad \mathbf d = G \begin{pmatrix}\Delta\mathbf r \\ b"
             r"\end{pmatrix} + \mathbf e")
    out.md("""
**Step 4: why at least 4 satellites.** The unknown vector $(\\Delta x, \\Delta y, \\Delta z,
b)$ has **4 entries**. With fewer than 4 equations there are infinitely many solutions;
with exactly 4 there is one; with 5 or more there are spare equations that let us check
consistency.

**Step 5: least squares.** With more equations than unknowns, choose the solution that
minimises the squared misfit $J = \\lVert \\mathbf d - G\\mathbf x \\rVert^2$. Setting the
derivative to zero, $\\partial J / \\partial \\mathbf x = -2G^T(\\mathbf d - G\\mathbf x) = 0$, gives
the normal equations and their solution:""")
    out.latex(r"G^T G\,\mathbf x = G^T \mathbf d \quad\Rightarrow\quad \mathbf x = (G^T G)^{-1}"
             r" G^T \mathbf d")
    out.md("""
**Step 6: HDOP.** If every range has the same noise $\\sigma$, the covariance of
$\\mathbf x$ is $\\sigma^2 (G^T G)^{-1}$. Its first two diagonal entries belong to east and
north, so the horizontal error is $\\sigma$ times""")
    out.latex(r"\mathrm{HDOP} = \sqrt{\left[(G^T G)^{-1}\right]_{11} + \left[(G^T G)^{-1}"
             r"\right]_{22}}")

    sats = [s for s in row.epoch.satellites if s.tracked] if row else []
    if len(sats) >= 4:
        rows = [geometry_row(s) for s in sats]
        gtg = [[sum(r[i] * r[j] for r in rows) for j in range(4)] for i in range(4)]
        inv = invert_4x4(gtg)
        if inv is not None:
            hdop = math.sqrt(inv[0][0] + inv[1][1])
            s = sats[0]
            out.md(f"""
*Worked example with the {len(sats)} satellites tracked at the selected second.*
Satellite {s.id} is at azimuth {s.azimuth_deg:.0f}° and elevation {s.elevation_deg:.0f}°,
so its row is $({rows[0][0]:.2f},\\ {rows[0][1]:.2f},\\ {rows[0][2]:.2f},\\ 1)$. Stacking
all rows and multiplying:""")
            out.latex(r"G^T G = " + _matrix_latex(gtg) + r",\quad (G^T G)^{-1} = "
                     + _matrix_latex(inv, "{:.3f}"))
            out.latex(rf"\mathrm{{HDOP}} = \sqrt{{{inv[0][0]:.3f} + {inv[1][1]:.3f}}} = "
                     rf"{hdop:.2f}")
            out.md(f"With 2 m range noise this means about {2 * hdop:.1f} m horizontal "
                        "error. Under 2 is good, over 5 poor.")
    else:
        out.md("*Pick a second with 4 or more tracked satellites to see a worked "
                    "example with real numbers.*")
    return out


def cn0() -> Blocks:
    out = Blocks()
    out.md("""
**Symbols.** $C$ is the received carrier (signal) power in watts, $N_0$ the noise power
per hertz of bandwidth (watts per hertz). Their ratio has units of hertz; in decibels:""")
    out.latex(r"C/N_0\,[\mathrm{dB\text{-}Hz}] = 10 \log_{10}\!\left(\frac{C}{N_0}\right)")
    out.md("""
*Example:* 45 dB-Hz means $C/N_0 = 10^{4.5} \\approx 31{,}600$ Hz. Every 3 dB is a factor of
2, every 10 dB a factor of 10.

**Why healthy satellites differ.** A satellite low on the horizon sends its signal through
more atmosphere, and the antenna is less sensitive near the horizon. Our simulator models
this as""")
    out.latex(r"C/N_0 \approx 35 + 15 \sin(el)")
    out.md(f"""
*Example:* at $el = 15°$: $35 + 15 \\times {math.sin(math.radians(15)):.3f} =
{35 + 15 * math.sin(math.radians(15)):.1f}$ dB-Hz; at $el = 75°$:
${35 + 15 * math.sin(math.radians(75)):.1f}$ dB-Hz. Real satellites therefore spread over
about 10 dB.

**Jamming as lost dB.** A jammer raises $N_0$. If the noise becomes 100 times stronger,
$C/N_0$ falls by $10\\log_{{10}}(100) = 20$ dB.

*Example:* a satellite at 45 dB-Hz drops to 25 dB-Hz, below the tracking threshold of 28,
so it is lost. Only satellites above 48 dB-Hz (high in the sky) would survive.""")
    return out


def dead_reckoning(cfg: GuardConfig) -> Blocks:
    out = Blocks()
    v, psi = 6.17, 90.3
    growth = cfg.drift_per_speed * v + cfg.drift_floor
    out.md("""
**Symbols.** $(x, y)$ east and north position (m), $v$ speed through the water (m/s),
$\\psi$ heading (degrees clockwise from north), $(c_E, c_N)$ the learned sea current (m/s),
$\\Delta t$ the time step (1 s), $\\sigma_x, \\sigma_y$ the uncertainty per axis (m).

**Step 1: split the speed into east and north parts.** Heading 0° is north and 90° east,
so the east part uses $\\sin\\psi$ and the north part $\\cos\\psi$. Then add the current,
which carries the whole ship:""")
    out.latex(r"x_{k+1} = x_k + (v \sin\psi + c_E)\,\Delta t, \qquad "
             r"y_{k+1} = y_k + (v \cos\psi + c_N)\,\Delta t")
    out.md(f"""
*Example:* $v = {v}$, $\\psi = {psi}°$, current $(0, 0.4)$:
$\\Delta x = {v} \\times {math.sin(math.radians(psi)):.5f} = {v * math.sin(math.radians(psi)):.2f}$ m,
$\\Delta y = {v} \\times ({math.cos(math.radians(psi)):.5f}) + 0.4 =
{v * math.cos(math.radians(psi)) + 0.4:.3f}$ m per second.

**Step 2: uncertainty growth.** Heading and speed errors are mostly **slow biases**
(a compass that reads 0.3° off keeps reading 0.3° off). A constant bias makes the
position error grow in proportion to time, so we let the uncertainty grow linearly:""")
    out.latex(rf"\sigma_{{k+1}} = \sigma_k + (a\,v + b)\,\Delta t, \quad a = "
             rf"{cfg.drift_per_speed},\ b = {cfg.drift_floor}\ \mathrm{{m/s}}")
    out.md(f"""
(Purely random errors would grow like $\\sqrt t$, which is slower; linear is the cautious
choice.)

*Example:* $a v + b = {cfg.drift_per_speed} \\times {v} + {cfg.drift_floor} = {growth:.3f}$ m/s.
After 600 s: $\\sigma = {cfg.start_sigma:.0f} + {growth:.3f} \\times 600 =
{cfg.start_sigma + growth * 600:.0f}$ m per axis, and the total
$\\sqrt{{\\sigma_x^2 + \\sigma_y^2}} = \\sqrt 2 \\times {cfg.start_sigma + growth * 600:.0f} =
{math.sqrt(2) * (cfg.start_sigma + growth * 600):.0f}$ m.""")
    return out


def gate(cfg: GuardConfig) -> Blocks:
    out = Blocks()
    out.md("""
**Symbols.** $d$ is the gap between the GNSS position and the dead-reckoning position (m),
$\\sigma$ the total dead-reckoning uncertainty (m), $g$ the gate (m).""")
    out.latex(rf"g = {cfg.gate_k:.0f}\,\sigma + {cfg.gate_floor_m:.0f}\ \mathrm{{m}}")
    out.md(f"""
**Why 3σ.** If an error is Gaussian with standard deviation $\\sigma$, it lies within
$\\pm 3\\sigma$ 99.73% of the time. A gap beyond $3\\sigma$ is therefore very unlikely to
be honest drift. The extra {cfg.gate_floor_m:.0f} m covers normal GNSS noise (about
{cfg.gnss_noise:.0f} m per axis), which σ does not include.

**Two thresholds.**""")
    out.latex(r"d > g \Rightarrow \text{SPOOFING}, \qquad \tfrac12 g < d \le g \Rightarrow "
             r"\text{DEGRADED}, \qquad d \le \tfrac12 g \Rightarrow \text{OK}")
    out.md("""
Beyond the gate the GNSS position is physically implausible, so we treat it as fake.
Between half the gate and the gate it is possible but unusually far off: we blend instead
of trusting it fully.

*Example:* $\\sigma = 10$ m gives $g = 3 \\times 10 + 10 = 40$ m and half-gate 20 m.
A gap of 15 m is OK, 25 m DEGRADED, 45 m SPOOFING.""")
    return out


def fusion() -> Blocks:
    out = Blocks()
    out.md("""
**Symbols.** Two independent estimates of the same quantity: $a$ with variance
$\\sigma^2$ (our dead reckoning) and $m$ with variance $\\sigma_m^2$ (a radar or depth fix).
We combine them as a weighted average with weight $K$ on the measurement:""")
    out.latex(r"\hat z = (1 - K)\,a + K\,m = a + K\,(m - a)")
    out.md("**Step 1: variance of the average** (independent errors add their variances, "
                "each scaled by its weight squared):")
    out.latex(r"V(K) = (1-K)^2 \sigma^2 + K^2 \sigma_m^2")
    out.md("**Step 2: pick the K with the smallest variance.** Set the derivative to zero:")
    out.latex(r"\frac{dV}{dK} = -2(1-K)\sigma^2 + 2K\sigma_m^2 = 0 \;\Rightarrow\; "
             r"K = \frac{\sigma^2}{\sigma^2 + \sigma_m^2}")
    out.md("**Step 3: the new variance.** Substitute K back:")
    out.latex(r"V = \frac{\sigma_m^4 \sigma^2 + \sigma^4 \sigma_m^2}{(\sigma^2 + \sigma_m^2)^2}"
             r" = \frac{\sigma^2 \sigma_m^2}{\sigma^2 + \sigma_m^2} = (1 - K)\,\sigma^2")
    out.md("""
so the new standard deviation is $\\sigma\\sqrt{1-K}$, always smaller than either input.

*Example:* dead reckoning $a = 100$ m with $\\sigma = 30$ m; radar $m = 130$ m with
$\\sigma_m = 15$ m. $K = 900 / (900 + 225) = 0.8$, $\\hat z = 100 + 0.8 \\times 30 = 124$ m,
new $\\sigma = 30\\sqrt{0.2} = 13.4$ m.""")
    return out


def terrain(cfg: GuardConfig) -> Blocks:
    out = Blocks()
    out.md(f"""
**Symbols.** Over the last $N = {cfg.depth_window_s}$ seconds we recorded sounder depths
$d_i$ at dead-reckoning positions $(x_i, y_i)$. $D(x, y)$ is the chart depth, $s$ an
east-west shift, and the sounder noise $n_i$ is Gaussian with standard deviation
$\\sigma_d$.

**Step 1: the model.** If the true track is our track shifted by $s$:""")
    out.latex(r"d_i = D(x_i + s, y_i) + n_i, \qquad n_i \sim \mathcal N(0, \sigma_d^2)")
    out.md("**Step 2: likelihood.** The probability of all measurements given $s$ is")
    out.latex(r"L(s) = \prod_{i=1}^{N} \frac{1}{\sqrt{2\pi}\sigma_d} "
             r"\exp\!\left(-\frac{(d_i - D(x_i + s, y_i))^2}{2\sigma_d^2}\right)")
    out.md("**Step 3: maximise it.** Taking minus the logarithm turns the product into a "
                "sum; constants do not depend on $s$, so maximising $L$ is the same as "
                "minimising the mean squared misfit:")
    out.latex(r"\mathrm{cost}(s) = \frac1N \sum_{i=1}^{N} \big(d_i - D(x_i + s, y_i)\big)^2")
    out.md(f"""
We try $s$ in steps of {cfg.depth_step_m:.0f} m and accept the best one if its cost is
below {cfg.depth_max_cost:.0f} m² and it is not at the edge of the search.

**Why a flat seabed cannot be matched.** If $D$ does not change with $x$, the cost is the
same for every $s$: the data carry no east-west information. More generally, with a seabed
slope $g$ (metres of depth per metre east), the shift error is about""")
    out.latex(r"\sigma_s \approx \frac{\sigma_d}{\sqrt N\,|g|}")
    out.md(f"""
*Example:* $\\sigma_d = 1$ m, $N = {cfg.depth_window_s}$, a sloping seabed with
$g = 0.017$ gives $\\sigma_s \\approx 1 / ({math.sqrt(cfg.depth_window_s):.2f} \\times 0.017)
\\approx {1 / (math.sqrt(cfg.depth_window_s) * 0.017):.0f}$ m. An almost flat seabed with
$g = 0.002$ gives about {1 / (math.sqrt(cfg.depth_window_s) * 0.002):.0f} m: useless.""")
    return out


def baseline(cfg: GuardConfig) -> Blocks:
    out = Blocks()
    a = cfg.baseline_learn_rate
    out.md("""
**Symbols.** $b_k$ is the learned 'normal' value (for example the mean C/N0), $m_k$ this
second's measurement, $\\alpha$ the learning rate.""")
    out.latex(rf"b_{{k+1}} = b_k + \alpha\,(m_k - b_k), \qquad \alpha = {a}")
    out.md(f"""
This is an **exponential average**: old values fade by a factor $(1 - \\alpha)$ each
second. After a sudden step change, the remaining gap after $k$ seconds is
$(1-\\alpha)^k \\approx e^{{-\\alpha k}}$, so the **time constant** is
$1/\\alpha = {1 / a:.0f}$ s: after {1 / a:.0f} s, 63% of a change has been learned.

*Example:* normal C/N0 is 45, and a spoofer makes it 52 (+7 dB). If learning continued,
after 20 s the baseline would be $45 + 7 \\times (1 - 0.95^{{20}}) =
{45 + 7 * (1 - (1 - a) ** 20):.1f}$, and after 60 s
{45 + 7 * (1 - (1 - a) ** 60):.1f}, so the +5 dB alarm would go quiet.

**That is why learning is frozen whenever GNSS is not trusted:** a spoofer must not be able
to teach the guard a fake 'normal'.""")
    return out


def _state_machine_svg(cfg: GuardConfig) -> str:
    """The same diagram as the DOT source, drawn by hand for browsers."""
    def box(x, y, w, label, fill):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="40" rx="10" fill="{fill}" '
                f'stroke="#333"/><text x="{x + w / 2}" y="{y + 25}" text-anchor="middle">'
                f'{label}</text>')

    def arrow(path, label, lx, ly):
        return (f'<path d="{path}" fill="none" stroke="#333" stroke-width="1.5" '
                f'marker-end="url(#head)"/><text x="{lx}" y="{ly}" font-size="12" '
                f'text-anchor="middle">{label}</text>')

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 270" '
        'font-family="Helvetica, Arial, sans-serif" font-size="13" role="img" '
        'aria-label="State machine diagram">',
        '<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
        'markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>',
        box(20, 110, 120, "TRUSTED", "#c8e6c9"),
        box(220, 15, 130, "DEGRADED", "#ffe0a3"),
        box(300, 110, 220, "LOST / JAMMING / SPOOFING", "#f6c1c0"),
        box(600, 200, 140, "RECOVERING", "#c6dcf5"),
        arrow("M90,110 Q120,30 218,32", "DEGRADED verdict", 105, 55),
        arrow(f"M230,57 Q180,95 142,120", f"{cfg.recover_soft_s} clean s", 205, 105),
        arrow("M142,135 L298,135", "hard verdict", 220, 128),
        arrow("M330,57 L385,108", "hard verdict", 395, 80),
        arrow("M520,140 Q580,150 610,198", "clean second", 595, 160),
        arrow("M600,228 Q470,215 445,153", "hard verdict (count resets)", 500, 235),
        arrow("M670,242 L670,262 L80,262 L80,153", f"{cfg.recover_hard_s} clean s", 380, 256),
        "</svg>",
    ]
    return "".join(parts)


def state_machine(cfg: GuardConfig) -> Blocks:
    out = Blocks()
    out.md("Each second the checks produce a **verdict**; the state machine turns "
                "verdicts into a **state**, with memory.")
    out.diagram(f"""
digraph G {{
  rankdir=LR; node [shape=box, style="rounded,filled", fontname=Helvetica];
  TRUSTED [fillcolor="#c8e6c9"]; DEGRADED [fillcolor="#ffe0a3"];
  RECOVERING [fillcolor="#c6dcf5"];
  BAD [label="LOST / JAMMING / SPOOFING", fillcolor="#f6c1c0"];
  TRUSTED -> DEGRADED [label="DEGRADED verdict"];
  DEGRADED -> TRUSTED [label="{cfg.recover_soft_s} clean s"];
  TRUSTED -> BAD [label="hard verdict"]; DEGRADED -> BAD [label="hard verdict"];
  BAD -> RECOVERING [label="clean second"];
  RECOVERING -> BAD [label="hard verdict (count resets)"];
  RECOVERING -> TRUSTED [label="{cfg.recover_hard_s} clean s"];
}}""", _state_machine_svg(cfg))
    out.md(f"""
| Current state | Verdict this second | Next state | Clean-second count |
|---|---|---|---|
| any | LOST / JAMMING / SPOOFING | that verdict | reset to 0, need {cfg.recover_hard_s} |
| TRUSTED | DEGRADED | DEGRADED | 0, need {cfg.recover_soft_s} |
| DEGRADED | DEGRADED | DEGRADED | reset to 0 |
| LOST / JAMMING / SPOOFING / RECOVERING | DEGRADED | unchanged | paused (no count, no reset) |
| not TRUSTED | OK | TRUSTED if count reaches the need, else RECOVERING (from a hard state) | +1 |
| TRUSTED | OK | TRUSTED | - |

*Example:* jamming ends at $t = 6000$ s. Clean seconds 6000, 6001, ... count 1, 2, ...;
at $t = 6059$ the count reaches {cfg.recover_hard_s} and the state becomes TRUSTED.""")
    return out


def statistics_section(row: Optional[Row], cfg: GuardConfig) -> Blocks:
    out = Blocks()
    out.md("""
**Symbols.** $x_1, \\dots, x_n$ are the C/N0 values of the $n$ tracked satellites.""")
    out.latex(r"\mu = \frac1n \sum_{i=1}^n x_i, \qquad "
             r"\sigma = \sqrt{\frac1n \sum_{i=1}^n (x_i - \mu)^2}")
    out.md(f"""
($\\sigma$ here is the *population* standard deviation: we describe these satellites, we
do not estimate anything beyond them.)

**Why a low spread is a clue.** Real satellites are at different elevations, so their
strengths differ by several dB (σ ≈ 4). A spoofer sends all its fake satellites from one
antenna, so they arrive equally strong (σ well below 1). The guard raises SPOOFING when
σ < {cfg.min_spread_db:.0f} dB-Hz.""")
    values = [s.cn0_dbhz for s in row.epoch.tracked] if row else []
    if len(values) >= 2:
        mu = statistics.fmean(values)
        sigma = statistics.pstdev(values)
        shown = ", ".join(f"{v:.1f}" for v in values)
        out.md(f"""
*Worked example with the selected second:* values {shown}.
$\\mu = {mu:.2f}$ dB-Hz, $\\sigma = {sigma:.2f}$ dB-Hz, so the spread check
**{"passes" if sigma >= cfg.min_spread_db else "fails"}**.""")
    return out


SECTIONS = (
    ("1. Position from satellites (least squares and HDOP)", "position"),
    ("2. C/N0: signal strength in dB-Hz", "cn0"),
    ("3. Dead reckoning", "dr"),
    ("4. The gate: DEGRADED and SPOOFING", "gate"),
    ("5. Fusion: combining two estimates", "fusion"),
    ("6. Terrain (depth) matching", "terrain"),
    ("7. Baseline learning", "baseline"),
    ("8. The 60-second rule and the state machine", "machine"),
    ("9. Statistics: mean and spread of C/N0", "stats"),
)



def derivation_sections(cfg: GuardConfig, row: Optional[Row]) -> List[Tuple[str, Blocks]]:
    """(title, blocks) for every derivation; row supplies the live worked examples."""
    builders = {
        "position": lambda: position_from_satellites(row),
        "cn0": cn0,
        "dr": lambda: dead_reckoning(cfg),
        "gate": lambda: gate(cfg),
        "fusion": fusion,
        "terrain": lambda: terrain(cfg),
        "baseline": lambda: baseline(cfg),
        "machine": lambda: state_machine(cfg),
        "stats": lambda: statistics_section(row, cfg),
    }
    return [(title, builders[key]()) for title, key in SECTIONS]
