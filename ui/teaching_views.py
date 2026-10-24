"""Streamlit renderers for the shared teaching content (see teaching/)."""

from typing import Optional

import streamlit as st

from marine_guard import GuardConfig
from sim.runner import Row
from teaching.blocks import Blocks
from teaching.briefing import briefing_blocks, further_reading
from teaching.derivations import derivation_sections
from teaching.simple import simple_blocks


def render_blocks(blocks: Blocks) -> None:
    for block in blocks:
        if block["type"] == "md":
            st.markdown(block["text"])
        elif block["type"] == "latex":
            st.latex(block["text"])
        elif block["type"] == "diagram":
            st.graphviz_chart(block["dot"])


def render_briefing() -> None:
    render_blocks(briefing_blocks())
    with st.expander("Further reading"):
        st.markdown("\n".join(f"- [{title}]({url})" for title, url in further_reading()))


def render_simple(cfg: GuardConfig) -> None:
    render_blocks(simple_blocks(cfg))


def render_derivations(cfg: GuardConfig, row: Optional[Row]) -> None:
    st.markdown("Each derivation goes step by step, defines every symbol and ends with a "
                "worked example. Where it says *selected second*, the numbers come from the "
                "time slider on the Monitor tab.")
    for title, blocks in derivation_sections(cfg, row):
        with st.expander(title):
            render_blocks(blocks)
