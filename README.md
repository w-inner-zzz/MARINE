# MARINE – maritime GNSS trust monitor
Decides every second whether the satellite position can be trusted and navigates on dead reckoning + radar/depth fixes when it cannot. Backend: `marine_guard/` (standard library only); simulator: `sim/`; viewer: `app.py`.
Install: `pip install -r requirements.txt`
Test: `pytest`
Run: `streamlit run app.py`
