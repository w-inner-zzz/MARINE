"""'Simple' tab: the whole system in plain language, one worked example per idea."""

from marine_guard import GuardConfig

from .blocks import Blocks


def simple_blocks(cfg: GuardConfig) -> Blocks:
    out = Blocks()
    growth = cfg.drift_per_speed * 6.17 + cfg.drift_floor
    out.md(
        f"""
### 1. What is GNSS?
**GNSS** (Global Navigation Satellite System) is the family of satellite systems that tell
a receiver where it is: GPS (USA), Galileo (EU), GLONASS (Russia) and BeiDou (China).
Each satellite keeps broadcasting *"I am here, and the time is now ..."*.
The receiver measures how long each message took to arrive and turns that delay into a
distance.

*Analogy:* you hear thunder 3 seconds after the lightning, so the storm is about
3 × 340 m ≈ 1 km away. A GNSS receiver does the same with radio waves, which travel
300,000 km per second.

*Worked example:* a signal that took 0.0700 s to arrive came from
0.0700 × 299,792 km/s ≈ **20,985 km** away.

### 2. Why 4 satellites (and why we ask for 5)?
One distance puts you somewhere on a huge sphere around one satellite. Three distances
pin down a point in 3-D space. But the receiver's own clock is cheap and slightly wrong,
so the clock error is a **fourth unknown**. Four unknowns (east, north, up, clock) need
**4 satellites**. A **5th** gives one spare measurement, so we can test that they all
agree.

*Worked example:* a clock error of just 1 microsecond (0.000001 s) is a distance error of
0.000001 × 300,000,000 m/s = **300 m**. That is why the clock must be solved for.

### 3. What are jamming and spoofing?
- **Jamming** is shouting over the satellites. The satellites are very quiet (they are
  20,000 km away), so a small transmitter nearby can drown them out. Signs: background
  noise goes up, satellites fade, and the position jumps or disappears.
- **Spoofing** is whispering lies in the satellites' voice. A transmitter sends fake
  satellite signals so the receiver calculates a confident but **wrong** position.

*Worked example:* in our crude spoofing scenario, all 12 fake satellites are about 52 dB-Hz
loud with a spread of only 0.6, while real ones range from about 38 to 50 with a spread of
about 4. They are too loud and too alike.

### 4. What does the guard check?
Every second it asks ten questions, in a fixed order, and the first "no" decides:
1. Is the background noise normal? 2. Are there at least {cfg.min_sats} satellites?
3. Are the satellites as loud as usual? 4. Do they differ from each other like real ones?
5. Are they not *too* loud? 6. Is the receiver clock steady? 7. Is the position where the
ship could physically be? 8. Is it on water? 9. Does the depth under the keel match the
chart? 10. Do GNSS and dead reckoning agree closely?

*Worked example:* noise floor normally 20 dB; it reads 35 dB, which is +15 dB, more than
the +{cfg.agc_jump_db:.0f} dB limit, so the verdict is **JAMMING** (question 1 already says
"no").

### 5. What is dead reckoning?
**Dead reckoning** is navigating by "I started here, went this way, this fast, for this
long". It needs only the compass (heading), the speed log (speed through the water) and a
clock: no satellites. Its weakness: small errors add up, so the **uncertainty grows**.

*Analogy:* walking across a dark room by counting steps. After a few steps you know where
you are; after a hundred, you are less sure.

*Worked example:* at 12 knots (6.17 m/s) heading east for 60 s the ship moves
6.17 × 60 ≈ **370 m** east. Our model adds about {growth:.2f} m of uncertainty per axis
every second, so after 10 minutes the uncertainty is about
{cfg.start_sigma:.0f} + {growth:.2f} × 600 ≈ **{cfg.start_sigma + growth * 600:.0f} m**
per axis, unless radar or depth fixes shrink it.

### 6. Why the 60-second rule?
Interference often comes and goes. If the guard trusted GNSS again the moment one second
looked clean, it could flip back and forth, or be fooled by a spoofer that pauses for a
moment. So after jamming, spoofing or signal loss, GNSS must be clean for
**{cfg.recover_hard_s} seconds in a row** (after a milder DEGRADED period:
{cfg.recover_soft_s} seconds).

*Worked example:* jamming stops at 100:00 min. The earliest the ship trusts GNSS again
is 101:00 min, and any new failure restarts the count.

### 7. Why the Baltic chart is the backup reference
The **stored chart** (coastline and seabed depths) was surveyed long before the voyage
and sits on board: **it does not depend on satellites**, so a jammer or spoofer cannot
change it.
- The **radar** measures the distance to the coast; the chart says where the coast is,
  so we learn how far north we are.
- The **depth sounder** measures the water under the keel; sliding the recorded depth
  profile along the chart's seabed shows where we are east-west.

*Worked example:* the chart puts the coast 34,190 m north of our reference point, and the
radar says the coast is 34,180 m ahead to the north. So we are 34,190 − 34,180 = **10 m**
north of the reference point, whatever the satellites claim.
"""
    )
    return out
