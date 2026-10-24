"""Sources cited in the app. Wording in the app stays close to what these say."""

SOURCES = {
    "sma": ("Swedish Maritime Administration warns of large-scale GPS disruptions "
            "(report by YACHT, June 2025)",
            "https://www.yacht.de/en/sailing-knowledge/navigation/"
            "baltic-sea-swedish-maritime-administration-warns-of-large-scale-gps-disruptions/"),
    "sma_notices": ("Swedish Maritime Administration - navigational warnings",
                    "https://navvarn.sjofartsverket.se/"),
    "imo5037": ("IMO Circular Letter No. 5037 (19 June 2025), communication from Estonia "
                "and Finland on GNSS interference (copy published by the Hong Kong Marine "
                "Department)",
                "https://www.mardep.gov.hk/filemanager/en/share/faq/pdf/gss250709a1.pdf"),
    "fi_ee_warning": ("Traficom: Finland and Estonia warn vessels in the Gulf of Finland "
                      "of an increase in GNSS disruptions",
                      "https://www.traficom.fi/en/news/"
                      "finland-and-estonia-warn-vessels-gulf-finland-increase-gnss-disruptions"),
    "ee_warning": ("Estonian Transport Administration: Estonia and Finland warn ships in the "
                   "Gulf of Finland about increased GNSS interference",
                   "https://transpordiamet.ee/en/news/"
                   "eesti-ja-soome-hoiatavad-laevu-soome-lahes-sagenenud-gnss-hairete-eest"),
    "traficom_2024": ("Traficom: situational picture of disturbances to satellite navigation "
                      "in Finland, 2024",
                      "https://www.traficom.fi/en/news/"
                      "situational-picture-disturbances-satellite-navigation-finland-2024"),
    "traficom_stats": ("Traficom: satellite navigation service interference in Finland "
                       "(statistics)",
                       "https://tieto.traficom.fi/en/statistics/"
                       "satellite-navigation-service-interference-finland"),
    "traficom_boating": ("Traficom: GPS interference increased in water areas - navigation "
                         "skills and the master's responsibility are emphasised",
                         "https://www.traficom.fi/en/news/gps-interference-increased-water-"
                         "areas-navigation-skills-and-masters-responsibility-are-emphasised-boating"),
    "yle_2800": ("Yle: GPS interference affecting almost all Finnish airports",
                 "https://yle.fi/a/74-20136751"),
    "gdansk": ("The Maritime Executive: Polish researchers detect ship-based GPS jammers "
               "in the Baltic Sea",
               "https://maritime-executive.com/article/"
               "polish-researchers-detect-ship-based-gps-jammers-in-baltic-sea"),
    "colreg": ("IMO: Convention on the International Regulations for Preventing "
               "Collisions at Sea (COLREG)",
               "https://www.imo.org/en/About/Conventions/Pages/COLREG.aspx"),
    "solas_v": ("IMO: Safety of navigation (SOLAS Chapter V)",
                "https://www.imo.org/en/OurWork/Safety/Pages/NavigationDefault.aspx"),
    "emodnet": ("EMODnet Bathymetry (European seabed depth data)",
                "https://emodnet.ec.europa.eu/en/bathymetry"),
    "land_mask": ("global-land-mask (Python package, GLOBE 1 km land/sea mask)",
                  "https://pypi.org/project/global-land-mask/"),
}


def link(key: str, text: str = None) -> str:
    title, url = SOURCES[key]
    return f"[{text or title}]({url})"
