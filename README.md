# MARINE – Baltic Sea GNSS trust monitor (teaching website)
Decides every second whether the satellite position can be trusted and keeps navigating on dead reckoning + radar/depth fixes when it cannot; set in the Gulf of Finland. Backend: `marine_guard/` (standard library only); simulator: `sim/`; texts: `teaching/`; website: `web/` (data from `python export_web.py`); optional Streamlit app: `app.py`.
Install: `pip install -r requirements.txt` (optional, needs internet: `python -m sim.bathymetry download` then `python export_web.py` for real EMODnet depths; otherwise the depth chart is SYNTHETIC and labelled so).
Test: `pytest`
Run the website: open `web/index.html` in a browser, or in VS Code use Run ▸ "Open website (Chrome)" (or right-click `web/index.html` ▸ "Open with Live Server"); after changing Python code run `python export_web.py`. Streamlit version: `streamlit run app.py`.
