# MARINE – Baltic Sea GNSS trust monitor (teaching app)
Decides every second whether the satellite position can be trusted and keeps navigating on dead reckoning + radar/depth fixes when it cannot; set in the Gulf of Finland. Backend: `marine_guard/` (standard library only); simulator: `sim/`; app: `app.py` + `ui/`.
Install: `pip install -r requirements.txt` (optional, needs internet: `python -m sim.bathymetry download` for real EMODnet depths; otherwise the depth chart is SYNTHETIC and labelled so).
Test: `pytest`
Run: `streamlit run app.py`
