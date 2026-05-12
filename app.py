"""
Noodsteunpunten Vergelijkingsapp
==================================
Streamlit app voor het vergelijken van optimalisatie-experimenten.
Wijst naar een map met .gpkg + .json bestanden (output van location_picker notebook).

Installeren en draaien:
    pip install streamlit geopandas folium streamlit-folium plotly fiona
    streamlit run app.py
"""

import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
import os
from pathlib import Path

# ─────────────────────────────────────────────
# Pagina config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Noodsteunpunten Vergelijking",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

    .main-title { font-size: 2rem; font-weight: 600; color: #0a2540; letter-spacing: -0.5px; }
    .sub-title { font-size: 1rem; color: #4a6080; margin-bottom: 1.5rem; font-weight: 300; }

    .exp-card {
        background: #f0f6ff; border: 1px solid #c8ddf5;
        border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 1rem;
        height: 100%;
    }
    .exp-name { font-size: 1rem; font-weight: 600; color: #0a2540; margin-bottom: 0.4rem; }
    .exp-meta { font-size: 0.75rem; color: #0a5fc4; margin-bottom: 0.4rem; font-family: 'DM Mono', monospace; }
    .exp-desc { font-size: 0.85rem; color: #4a6080; line-height: 1.5; }

    .metric-card {
        background: white; border: 1px solid #e0ecf8;
        border-radius: 8px; padding: 0.6rem 0.8rem;
        text-align: center; margin-bottom: 0.4rem;
    }
    .metric-value { font-size: 1.3rem; font-weight: 600; color: #0a5fc4; font-family: 'DM Mono', monospace; }
    .metric-best { border: 2px solid #2ecc71 !important; }
    .metric-worst { border: 2px solid #e74c3c !important; }

    .section-header {
        font-size: 0.85rem; font-weight: 600; color: #0a2540;
        text-transform: uppercase; letter-spacing: 0.1em;
        margin: 1.25rem 0 0.6rem 0; padding-bottom: 0.3rem;
        border-bottom: 2px solid #0a5fc4;
    }

    [data-testid="stSidebar"] { background: #0a2540; }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] label {
        color: #a0bcd8 !important; font-size: 0.78rem;
        text-transform: uppercase; letter-spacing: 0.08em;
    }
    [data-testid="stSidebar"] .stTextInput input {
        background: #1a3a5c; border: 1px solid #2a5a8c; color: white !important;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def scan_experiment_folder(folder: str) -> dict:
    """
    Scan een map op .gpkg bestanden. Laad bijbehorende .json metadata als die bestaat.
    Geeft dict terug: {bestandsnaam_zonder_ext: {label, description, path, ...}}
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        return {}

    found = {}
    for gpkg_file in sorted(folder_path.glob("*.gpkg")):
        name = gpkg_file.stem
        json_file = folder_path / f"{name}.json"

        meta = {"label": name, "description": "", "gemeente": "", "experiment": name}
        if json_file.exists():
            try:
                with open(json_file, encoding="utf-8") as f:
                    meta.update(json.load(f))
            except Exception:
                pass

        meta["path"] = str(gpkg_file)
        found[name] = meta

    return found


@st.cache_data
def load_gpkg_from_path(path: str) -> dict:
    import fiona
    layers = fiona.listlayers(path)
    return {layer: gpd.read_file(path, layer=layer).to_crs(epsg=4326) for layer in layers}


def get_center(gdf: gpd.GeoDataFrame) -> tuple:
    b = gdf.total_bounds
    return ((b[1] + b[3]) / 2, (b[0] + b[2]) / 2)


def build_sample_map(gdf_res: gpd.GeoDataFrame, gdf_park: gpd.GeoDataFrame, n: int = 300) -> folium.Map:
    m = folium.Map(location=get_center(gdf_res), zoom_start=13, tiles="CartoDB positron")
    unique_lots = gdf_res["assigned_parking_lot"].dropna().unique()
    palette = px.colors.qualitative.Safe + px.colors.qualitative.Vivid
    lot_colors = {lot: palette[i % len(palette)] for i, lot in enumerate(unique_lots)}

    for _, row in gdf_park.iterrows():
        lid = row.get("parking_lot_id", row.name)
        color = lot_colors.get(lid, "#0a5fc4")
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda _, c=color: {"fillColor": c, "color": "#0a2540", "weight": 2, "fillOpacity": 0.8},
            tooltip=folium.Tooltip(f"<b>Punt {lid}</b>"),
        ).add_to(m)

    for _, row in gdf_res.sample(min(n, len(gdf_res)), random_state=42).iterrows():
        lid = row.get("assigned_parking_lot")
        color = lot_colors.get(lid, "#aaa")
        folium.CircleMarker(
            location=(row.geometry.y, row.geometry.x),
            radius=3, color=color, fill=True,
            fill_color=color, fill_opacity=0.6,
            tooltip=f"Afstand: {row.get('distance_to_parking', '?')}m | Punt: {lid}",
        ).add_to(m)
    return m


def compute_metrics(gdf_res: gpd.GeoDataFrame, gdf_park: gpd.GeoDataFrame) -> dict:
    dist = gdf_res["distance_to_parking"].dropna()
    per_lot = gdf_res.groupby("assigned_parking_lot").size()
    return {
        "Gem. afstand (m)": int(dist.mean()),
        "Max. afstand (m)": int(dist.max()),
        "Mediaan afstand (m)": int(dist.median()),
        "% binnen 1km": round((dist <= 1000).mean() * 100, 1),
        "Max. belasting punt": int(per_lot.max()),
        "Distributiepunten": len(gdf_park),
    }


def render_metrics_table(selected_data: dict):
    higher_is_better = {"% binnen 1km"}
    all_metrics = {name: compute_metrics(d["residents"], d["parking_lots"]) for name, d in selected_data.items()}
    metric_keys = list(next(iter(all_metrics.values())).keys())

    st.markdown('<div class="section-header">Indicatoren vergelijking</div>', unsafe_allow_html=True)

    n = len(selected_data)
    header_cols = st.columns([1.8] + [1] * n)
    with header_cols[0]:
        st.markdown("<small><b>Indicator</b></small>", unsafe_allow_html=True)
    for i, (name, data) in enumerate(selected_data.items()):
        with header_cols[i + 1]:
            st.markdown(f"<small><b>{data['meta']['label']}</b></small>", unsafe_allow_html=True)

    for key in metric_keys:
        values = {name: all_metrics[name][key] for name in selected_data}
        if n > 1:
            best = max(values, key=lambda x: values[x]) if key in higher_is_better else min(values, key=lambda x: values[x])
            worst = min(values, key=lambda x: values[x]) if key in higher_is_better else max(values, key=lambda x: values[x])
        else:
            best = worst = None

        row_cols = st.columns([1.8] + [1] * n)
        with row_cols[0]:
            st.markdown(f"<small>{key}</small>", unsafe_allow_html=True)
        for i, name in enumerate(selected_data):
            css = "metric-card"
            if best and name == best:
                css += " metric-best"
            elif worst and name == worst:
                css += " metric-worst"
            with row_cols[i + 1]:
                st.markdown(f'<div class="{css}"><div class="metric-value">{values[name]}</div></div>', unsafe_allow_html=True)

    if n > 1:
        st.markdown("<small style='color:#4a6080'>🟢 beste &nbsp;|&nbsp; 🔴 slechtste</small>", unsafe_allow_html=True)


def render_distance_chart(selected_data: dict):
    st.markdown('<div class="section-header">Afstandsverdeling</div>', unsafe_allow_html=True)
    fig = go.Figure()
    exp_colors = ["#0a5fc4", "#e67e22", "#2ecc71", "#9b59b6", "#e74c3c"]
    for i, (name, data) in enumerate(selected_data.items()):
        dist = data["residents"]["distance_to_parking"].dropna()
        fig.add_trace(go.Histogram(
            x=dist, nbinsx=40,
            name=data["meta"]["label"],
            marker_color=exp_colors[i % len(exp_colors)],
            opacity=0.6,
        ))
    fig.add_vline(x=1000, line_dash="dash", line_color="#e63946",
                  annotation_text="1km norm", annotation_position="top right")
    fig.update_layout(
        barmode="overlay",
        xaxis_title="Afstand (m)", yaxis_title="Aantal bewoners",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="DM Sans", color="#0a2540"),
        margin=dict(l=20, r=20, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💧 Noodsteunpunten")
    st.markdown("---")

    folder_input = st.text_input(
        "Map met experimenten",
        value="data/processed/experimenten",
        help="Pad naar de map met .gpkg en .json bestanden (output van de notebook).",
    )

    available = scan_experiment_folder(folder_input)

    st.markdown("---")

    if not available:
        st.warning("Geen .gpkg bestanden gevonden in deze map.")
        selected_names = []
    else:
        st.markdown(f"**{len(available)} experiment(en) gevonden**")
        selected_names = []
        for name, meta in available.items():
            label = meta.get("label", name)
            gemeente = meta.get("gemeente", "")
            display_label = f"{label}" + (f" ({gemeente})" if gemeente else "")
            if st.checkbox(display_label, value=True, key=f"chk_{name}"):
                selected_names.append(name)

    st.markdown("---")
    st.markdown(
        "<small style='color:#a0bcd8'>Output van <code>location_picker.ipynb</code>.<br>"
        "Per experiment: <code>.gpkg</code> + <code>.json</code></small>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# Hoofdpagina
# ─────────────────────────────────────────────
st.markdown('<div class="main-title">💧 Nooddrinkwater Distributiepunten</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Vergelijking van optimalisatie-experimenten · NIPV Hackathon 2026</div>', unsafe_allow_html=True)

if not available:
    st.markdown("""
    <div style="background:#f8fafc; border:2px dashed #c8ddf5; border-radius:12px; padding:2rem; text-align:center; color:#4a6080;">
        <h3 style="color:#0a5fc4;">📂 Geen experimenten gevonden</h3>
        <p>Voer een geldig mappad in via de sidebar.<br>
        De map moet <code>.gpkg</code> bestanden bevatten (output van de notebook).</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if not selected_names:
    st.info("Selecteer minimaal één experiment via de sidebar.")
    st.stop()

# Data laden voor geselecteerde experimenten
selected_data = {}
for name in selected_names:
    meta = available[name]
    with st.spinner(f"{meta['label']} laden..."):
        try:
            layers = load_gpkg_from_path(meta["path"])
            if "residents" not in layers or "parking_lots" not in layers:
                st.warning(f"⚠️ {name}: lagen 'residents' of 'parking_lots' niet gevonden.")
                continue
            if "distance_to_parking" not in layers["residents"].columns:
                st.warning(f"⚠️ {name}: kolom 'distance_to_parking' ontbreekt.")
                continue
            selected_data[name] = {**layers, "meta": meta}
        except Exception as e:
            st.error(f"Fout bij laden {name}: {e}")

if not selected_data:
    st.error("Geen geldige experimenten geladen.")
    st.stop()

# ── Experiment beschrijvingen ──
st.markdown('<div class="section-header">Experimenten</div>', unsafe_allow_html=True)
desc_cols = st.columns(len(selected_data))
for i, (name, data) in enumerate(selected_data.items()):
    meta = data["meta"]
    with desc_cols[i]:
        st.markdown(f"""
        <div class="exp-card">
            <div class="exp-name">{meta.get('label', name)}</div>
            <div class="exp-meta">
                {meta.get('optimisation_class', '')} · {meta.get('assignment_method', '')}
                {(' · ' + meta.get('gemeente', '')) if meta.get('gemeente') else ''}
            </div>
            <div class="exp-desc">{meta.get('description', 'Geen beschrijving beschikbaar.')}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Indicatoren ──
render_metrics_table(selected_data)

# ── Kaarten ──
st.markdown('<div class="section-header">Kaarten (steekproef 300 bewoners)</div>', unsafe_allow_html=True)
map_cols = st.columns(len(selected_data))
for i, (name, data) in enumerate(selected_data.items()):
    with map_cols[i]:
        st.markdown(f"<small><b>{data['meta']['label']}</b></small>", unsafe_allow_html=True)
        with st.spinner("Kaart opbouwen..."):
            m = build_sample_map(data["residents"], data["parking_lots"])
            st_folium(m, width="100%", height=400, returned_objects=[], key=f"map_{i}_{name}")

# ── Afstandsverdeling ──
render_distance_chart(selected_data)

# ── Ruwe data ──
with st.expander("📋 Ruwe data bekijken"):
    for name, data in selected_data.items():
        st.markdown(f"**{data['meta']['label']}**")
        st.dataframe(
            data["residents"].drop(columns="geometry").sample(min(100, len(data["residents"]))),
            use_container_width=True,
        )