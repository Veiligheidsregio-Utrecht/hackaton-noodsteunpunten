# Noodsteunpunten Visualisatie App
Streamlit app voor het vergelijken van optimalisatie-experimenten voor nooddrinkwater distributiepunten.
Vereisten

Python 3.10+
Output van location_picker.ipynb (.gpkg + .json bestanden)

Installatie
bashpython -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install streamlit geopandas folium streamlit-folium plotly fiona
Gebruik
1. Genereer data via de notebook
Draai location_picker.ipynb volledig door. De output verschijnt automatisch in data/experimenten/.
Per experiment worden twee bestanden aangemaakt:

{gemeente}_{experiment}.gpkg — geodata met bewoners en distributiepunten
{gemeente}_{experiment}.json — metadata (label, beschrijving, parameters)

2. Start de app
streamlit run app.py
De app opent automatisch in je browser op http://localhost:8501.
3. Experimenten selecteren

Voer het mappad in via de sidebar (standaard: data/experimenten)
De app detecteert automatisch alle beschikbare experimenten
Vink aan welke experimenten je wil vergelijken

Wat de app toont
OnderdeelBeschrijvingExperimentbeschrijvingenLabel, algoritme en toelichting per experimentIndicatorenvergelijkingGem. afstand, max. afstand, % binnen 1km, belasting per puntKaartenSteekproef van 300 bewoners per experiment, ingekleurd per distributiepuntAfstandsverdelingHistogram van alle bewoners per experiment, met 1km-normRuwe dataTabel met sample van de onderliggende data
Groene rand = beste waarde · Rode rand = slechtste waarde (bij vergelijking van meerdere experimenten)
Beschikbare experimenten
De experimenten worden geconfigureerd in de notebook onder SETUP_EXPERIMENTS. Zie de notebook voor uitleg over beschikbare algoritmen en toewijzingsmethoden.