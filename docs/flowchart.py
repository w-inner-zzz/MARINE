"""Draw the diagnosis flow chart: how the guard turns its 10 checks into a
verdict each second, and how the verdict changes the state.

Run:  python docs/flowchart.py   (writes docs/diagnosis_flowchart.svg)

The check names, their order and the verdict each one gives are read from
marine_guard itself and the thresholds from GuardConfig, so the chart stays
in step with the code.
"""

import pathlib
import sys
from html import escape
from typing import List, Tuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from marine_guard import GnssEpoch, GuardConfig  # noqa: E402
from marine_guard import checks as chk  # noqa: E402
from teaching.palette import STATE_COLORS  # noqa: E402

OUT = ROOT / "docs" / "diagnosis_flowchart.svg"

VERDICT_COLORS = {s.value: c for s, c in STATE_COLORS.items()}
VERDICT_COLORS["OK"] = VERDICT_COLORS["TRUSTED"]

# Question asked by each check and, if the answer is yes, what it suggests.
QUESTIONS = {
    "Noise floor": ("Is the background radio noise more than +{agc_jump_db:g} dB above its learned normal?",
                    "a transmitter is drowning the satellite signals"),
    "Satellite count": ("Are fewer than {min_sats} satellites tracked, or is there no position?",
                        "too few satellites to fix and cross-check"),
    "Signal strength drop": ("Are the satellites on average more than {cn0_drop_db:g} dB quieter than normal?",
                             "all signals covered by noise at once"),
    "Signal spread": ("Do the satellites differ in strength by less than {min_spread_db:g} dB-Hz (std-dev)?",
                      "one transmitter faking many satellites"),
    "Signal strength rise": ("Are the satellites on average more than {cn0_rise_db:g} dB louder than normal?",
                             "louder than satellites 20,000 km away can be"),
    "Clock consistency": ("Has the receiver clock jumped more than {time_tol_s:g} s from normal?",
                          "fake signals carry wrong time"),
    "Position vs dead reckoning": ("Is GNSS further from dead reckoning than the gate "
                                   "({gate_k:g} x uncertainty + {gate_floor_m:g} m)?",
                                   "the ship cannot have moved there"),
    "Position on water": ("Is the GNSS position on land according to the chart?",
                          "a ship cannot be on land"),
    "Depth vs chart": ("Does the sounder disagree with the chart depth at the GNSS position "
                       "by more than {depth_tol_fraction:g} x depth + {depth_tol_m:g} m?",
                       "the water under the keel says we are elsewhere"),
    "Position agreement": ("Is GNSS further from dead reckoning than half the gate?",
                           "noisy but possible: blend with dead reckoning"),
}

GROUPS = (("Signal checks", 0, 5), ("Position checks", 6, 9))

# Layout (px)
WIDTH = 1180
TOP = 150
ROW = 92
DEC_X, DEC_W, DEC_H = 150, 560, 64
VER_X, VER_W, VER_H = 800, 340, 64
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def checks_in_code_order() -> List[Tuple[str, str]]:
    """(name, verdict if it fails) for every check, in the order the guard runs them."""
    ctx = chk.CheckContext(GnssEpoch(0, (), 20.0, None, None), chk.Baselines(45.0, 20.0, 0.01),
                           (0.0, 0.0), 5.0, None, None, GuardConfig())
    return [(c.name, c.verdict_if_failed) for c in chk.run_checks(ctx)]


def wrap(text: str, width: int) -> List[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line]


def text(x, y, content, size=14, weight=400, anchor="start", color="#15171a", italic=False):
    style = ' font-style="italic"' if italic else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" '
            f'text-anchor="{anchor}"{style}>{escape(content)}</text>')


def arrow(x1, y1, x2, y2, label=None, lx=0, ly=0):
    out = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="2" '
           f'marker-end="url(#head)"/>')
    if label:
        out += text(x1 + lx, y1 + ly, label, size=13, weight=700, color="#333")
    return out


def decision(y, number, name, question):
    """A hexagon: the decision shape used throughout."""
    x0, x1, mid = DEC_X, DEC_X + DEC_W, y + DEC_H / 2
    points = f"{x0 + 18},{y} {x1 - 18},{y} {x1},{mid} {x1 - 18},{y + DEC_H} {x0 + 18},{y + DEC_H} {x0},{mid}"
    out = f'<polygon points="{points}" fill="#f4f6fa" stroke="#1d2733" stroke-width="1.5"/>'
    out += text(x0 + 34, y + 22, f"{number}. {name}", size=15, weight=700)
    for i, line in enumerate(wrap(question, 80)):
        out += text(x0 + 34, y + 41 + 16 * i, line, size=13)
    return out


def verdict_box(y, verdict, reason):
    color = VERDICT_COLORS[verdict]
    out = (f'<rect x="{VER_X}" y="{y}" width="{VER_W}" height="{VER_H}" rx="10" fill="{color}"/>')
    out += text(VER_X + 16, y + 25, verdict, size=17, weight=800, color="#ffffff")
    for i, line in enumerate(wrap(reason, 48)):
        out += text(VER_X + 16, y + 44 + 15 * i, line, size=12.5, color="#ffffff")
    return out


def state_rules(y: int, cfg: GuardConfig) -> str:
    """Bottom section: what the verdict does to the state."""
    columns = (
        ("LOST / JAMMING / SPOOFING", VERDICT_COLORS["JAMMING"], [
            "State becomes that alarm.",
            "Ignore GNSS: navigate on dead reckoning + radar, depth and any aid.",
            f"Clean-second count reset to 0; {cfg.recover_hard_s} clean seconds needed.",
        ]),
        ("DEGRADED", VERDICT_COLORS["DEGRADED"], [
            f"From TRUSTED: state DEGRADED; {cfg.recover_soft_s} clean seconds needed.",
            "Already DEGRADED: count reset to 0.",
            "On backup (alarm or RECOVERING): count paused.",
        ]),
        ("OK", VERDICT_COLORS["OK"], [
            "TRUSTED: stay TRUSTED, use GNSS, learn what normal looks like.",
            "Otherwise count +1. When it reaches the need: TRUSTED again.",
            "Until then, after an alarm: RECOVERING (still on backup).",
        ]),
    )
    out = text(40, y, "Then: what the verdict does to the ship's state", size=20, weight=800)
    width = (WIDTH - 80 - 2 * 20) / 3
    for i, (title, color, lines) in enumerate(columns):
        x = 40 + i * (width + 20)
        out += f'<rect x="{x}" y="{y + 18}" width="{width}" height="172" rx="10" fill="#ffffff" stroke="{color}" stroke-width="3"/>'
        out += f'<rect x="{x}" y="{y + 18}" width="{width}" height="34" rx="10" fill="{color}"/>'
        out += text(x + 14, y + 41, f"Verdict {title}", size=15, weight=800, color="#ffffff")
        row = y + 74
        for line in lines:
            for j, part in enumerate(wrap(line, 46)):
                out += text(x + 14 + (0 if j == 0 else 12), row, ("• " if j == 0 else "") + part, size=13)
                row += 18
            row += 4
    return out


def build() -> str:
    cfg = GuardConfig()
    numbers = {k: v for k, v in vars(cfg).items() if isinstance(v, (int, float))}
    checks = checks_in_code_order()
    missing = {name for name, _ in checks} ^ set(QUESTIONS)
    if missing:
        raise SystemExit(f"Update QUESTIONS in docs/flowchart.py: {sorted(missing)}")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {{height}}" '
        f'font-family="{FONT}" role="img" aria-label="Diagnosis flow chart">',
        '<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>',
        f'<rect width="{WIDTH}" height="{{height}}" fill="#ffffff"/>',
        text(40, 44, "How the GNSS guard diagnoses the problem", size=26, weight=800),
        text(40, 70, "Every second, all 10 checks run in this order. The FIRST one that answers "
             "“yes” decides the verdict.", size=15, color="#444"),
        text(40, 92, "A check without data this second (e.g. no satellites, no GNSS position) is "
             "skipped: it neither passes nor fails.", size=13, color="#666", italic=True),
    ]
    start_y = TOP - 30
    parts.append(f'<rect x="{DEC_X + DEC_W / 2 - 150}" y="{start_y - 18}" width="300" height="34" '
                 f'rx="17" fill="#1d2733"/>')
    parts.append(text(DEC_X + DEC_W / 2, start_y + 4, "New GNSS reading + ship sensors", size=14,
                      weight=700, anchor="middle", color="#ffffff"))
    parts.append(arrow(DEC_X + DEC_W / 2, start_y + 16, DEC_X + DEC_W / 2, TOP - 2))

    for i, (name, verdict) in enumerate(checks):
        y = TOP + i * ROW
        question, reason = QUESTIONS[name]
        parts.append(decision(y, i + 1, name, question.format(**numbers)))
        parts.append(arrow(DEC_X + DEC_W, y + DEC_H / 2, VER_X - 2, y + DEC_H / 2, "yes", 26, -8))
        parts.append(verdict_box(y, verdict, reason))
        parts.append(arrow(DEC_X + DEC_W / 2, y + DEC_H, DEC_X + DEC_W / 2, y + ROW - 2,
                           "no", 10, 20))

    for title, first, last in GROUPS:
        y0, y1 = TOP + first * ROW, TOP + last * ROW + DEC_H
        parts.append(f'<line x1="118" y1="{y0}" x2="118" y2="{y1}" stroke="#8a8986" stroke-width="3"/>')
        mid = (y0 + y1) / 2
        parts.append(f'<text x="100" y="{mid}" font-size="15" font-weight="700" fill="#6b6f76" '
                     f'text-anchor="middle" transform="rotate(-90 100 {mid})">{escape(title)}</text>')

    ok_y = TOP + len(checks) * ROW
    parts.append(f'<rect x="{DEC_X + DEC_W / 2 - 170}" y="{ok_y}" width="340" height="{VER_H}" rx="10" '
                 f'fill="{VERDICT_COLORS["OK"]}"/>')
    parts.append(text(DEC_X + DEC_W / 2, ok_y + 27, "All checks passed: verdict OK", size=17,
                      weight=800, anchor="middle", color="#ffffff"))
    parts.append(text(DEC_X + DEC_W / 2, ok_y + 47, "GNSS can be used", size=13, anchor="middle",
                      color="#ffffff"))

    rules_y = ok_y + VER_H + 70
    parts.append(state_rules(rules_y, cfg))
    height = rules_y + 215
    parts.append("</svg>")
    return "".join(parts).replace("{height}", str(height))


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")
