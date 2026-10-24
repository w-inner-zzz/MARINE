"""Content blocks: a small, front-end-neutral way to describe teaching text.

A block is a dict with a "type":
  md       - Markdown text (may contain $inline$ maths)
  latex    - one displayed formula (LaTeX)
  diagram  - a diagram, given both as Graphviz DOT and as ready-made SVG
"""

from typing import Dict, List

Block = Dict[str, str]


class Blocks(list):
    """A list of blocks with helpers to append them."""

    def md(self, text: str) -> None:
        self.append({"type": "md", "text": text})

    def latex(self, formula: str) -> None:
        self.append({"type": "latex", "text": formula})

    def diagram(self, dot: str, svg: str) -> None:
        self.append({"type": "diagram", "dot": dot, "svg": svg})


def as_list(blocks: Blocks) -> List[Block]:
    return [dict(b) for b in blocks]
