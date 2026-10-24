"""'Why the Baltic Sea?' briefing. Cautious wording; every claim is linked."""

from typing import List, Tuple

from .blocks import Blocks
from .sources import SOURCES, link


def briefing_blocks() -> Blocks:
    out = Blocks()
    out.md(
        f"""
**GNSS** (Global Navigation Satellite System: GPS, Galileo, GLONASS, BeiDou) is how
almost every ship knows where it is. In the Baltic Sea, that signal is often disturbed.

**What has been reported**

- The Swedish Maritime Administration has said that GPS interference is to be expected
  in large parts of the Baltic Sea: the southern, central and northern Baltic, the Gulf
  of Finland and the Åland Sea ({link("sma", "report")};
  {link("sma_notices", "current navigational warnings")}).
- The Gulf of Finland, especially its eastern part near **Kotka-Hamina**, is described
  as the highest-risk area ({link("traficom_2024", "Traficom")};
  {link("fi_ee_warning", "Finnish-Estonian warning")}).
- Finland's transport authority Traficom received about **2,800** reports of satellite
  navigation interference in 2024, more than ten times the year before (about 200 in
  2023), according to {link("yle_2800", "Yle")}; most of those reports concern aviation.
  See also {link("traficom_stats", "Traficom's statistics")}.
- According to the Finnish and Estonian authorities, most incidents are **jamming**
  (receivers lose satellites), and all satellite systems (GPS, Galileo, GLONASS, BeiDou)
  can be affected. Warning signs include **position jumps of 10 to 100 m** and an
  **erratic speed over ground**, and the **AIS** positions of other ships can also be
  wrong ({link("imo5037", "IMO Circular Letter No. 5037")};
  {link("ee_warning", "Estonian Transport Administration")}).
- A Polish study (June to December 2024) recorded disturbances lasting **over seven
  hours** near Gdańsk and suggested the sources may be **moving, at sea**
  ({link("gdansk", "The Maritime Executive")}).

**Why a wrong position is dangerous here**

The Baltic is **shallow** (often only tens of metres deep, with many rocks and shoals),
its **shipping lanes are busy**, it has **narrow straits** and **many coasts close
together**. A position that is wrong by a few hundred metres can put a ship on the wrong
side of a shoal or into a traffic lane going the other way.

*This app simulates such events and shows how a ship could notice them and keep
navigating safely. It does not say who causes them.*
"""
    )
    return out


def further_reading() -> List[Tuple[str, str]]:
    """(title, url) of every source, for a 'further reading' list."""
    return list(SOURCES.values())
