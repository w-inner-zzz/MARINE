"""Plain-language reading guides shown next to charts and numbers (shared by the
Streamlit app and the static website)."""

CAPTIONS = {
    "satellite_table": (
        "Azimuth is the compass direction to the satellite, elevation its height above "
        "the horizon (90° = straight up). 'Tracked' means the receiver uses it."
    ),
    "noise_floor": (
        "The background radio hiss. A jump of more than 3 dB above the learned normal "
        "means someone is transmitting noise."
    ),
    "satellite_count": (
        "4 unknowns (east, north, up, clock) need 4 satellites; the 5th lets us test "
        "that they agree."
    ),
    "hdop": (
        "How much the satellite layout magnifies errors. Under 2 is good (spread around "
        "the sky), over 5 poor."
    ),
    "time_error": (
        "The receiver's clock offset. It should stay steady; a sudden jump of 100 ms or "
        "more is suspicious."
    ),
    "gnss_position": (
        "What the receiver says (latitude north, longitude east). Not yet checked: it "
        "may be wrong."
    ),
    "sky": (
        "Each dot is a satellite seen from the ship: the centre is straight up, the "
        "edge the horizon. Real satellites are spread around the sky; fakes from one "
        "transmitter all sit in one direction."
    ),
    "cn0_bars": (
        "C/N0 is how loud each satellite is compared with the background noise. Healthy "
        "satellites sit in the green band and differ from each other; below the dashed "
        "line the receiver loses them."
    ),
    "cn0_history": (
        "Thin lines are single satellites, the thick line their average. A sudden drop "
        "of every line together means jamming; lines bunching together at a high level "
        "means spoofing."
    ),
    "count_history": (
        "Below the green line (5) the position can no longer be cross-checked; below 4 "
        "there is no position at all."
    ),
    "noise_history": (
        "If the blue line crosses the red dashed line, the noise is more than 3 dB "
        "above normal: the first sign of jamming."
    ),
    "jump_history": (
        "At 12 knots the ship moves about 6 m each second, so the line should stay near "
        "the dotted speed line. Spikes are position jumps."
    ),
    "route_map": (
        "Latitude runs up, longitude across; both axes are scaled so 1 km looks the "
        "same either way. Stars mark the moments the guard raised an alarm, with the "
        "check that decided. A red ✕ marks where trusting GNSS would have led towards "
        "land or shallow water."
    ),
    "error_chart": (
        "Distance between the reported position and the real one, on a log scale (each "
        "grid line is 10 times more). The guard (green) should stay low while the naive "
        "receiver (red) runs away during the event."
    ),
    "closeup_map": (
        "The green circle is the guard's uncertainty: the ship should be somewhere "
        "inside it. It grows on dead reckoning and shrinks with each radar (▼) or depth "
        "(◆) fix."
    ),
    "overview_map": (
        "The whole Baltic. The blue line is this voyage in the Gulf of Finland."
    ),
}

SECTION_TEXT = {
    "input": ("Before deciding anything, look at the raw input: which satellites are "
              "heard, how loud, from where, and what position the receiver claims."),
    "checks": ("The guard runs ten checks every second, top to bottom. All are evaluated, "
               "but the **first one that fails decides** the verdict, so the order matters: "
               "the most certain signs (noise, missing satellites) come first."),
    "map": ("**Red**: what GNSS reported while it could not be trusted (the path a "
            "GNSS-following autopilot would believe). **Green**: the guard's backup track, "
            "navigating without GNSS. **Grey dotted**: the real track, which only a "
            "simulation can know. While GNSS is trusted only the blue ship track is drawn."),
}
