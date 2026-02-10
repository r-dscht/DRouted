import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_searchbox import st_searchbox
from streamlit_js_eval import get_geolocation
import time
import random

# Core functies importeren
from core.route_logic import search_address, calculate_round_trip, convert_geojson_to_gpx

# --- 1. CONFIGURATIE ---
st.set_page_config(
    page_title="DRouted",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS STYLING (Strak & Schoon) ---
st.markdown("""
<style>
    /* Verberg standaard Streamlit elementen */
    #MainMenu, footer, header {visibility: hidden;}

    /* Zorg dat de app het hele scherm gebruikt zonder witte randen */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
        max-width: 800px; /* Zorgt dat het op PC niet te breed uitrekt */
        margin: 0 auto;   /* Centreer op PC */
    }

    /* === HEADER STIJL === */
    .app-header {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 15px;
        font-family: 'Helvetica Neue', sans-serif;
    }
    .app-title {
        font-size: 1.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }

    /* === KNOPPEN STYLEN === */
    /* De grote actie knop */
    div.stButton > button {
        width: 100%;
        border-radius: 12px;
        height: 55px;
        font-size: 18px !important;
        font-weight: 700 !important;
        border: none;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        color: white;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        transition: transform 0.1s;
    }
    div.stButton > button:active {
        transform: scale(0.98);
    }

    /* Specifieke styling voor de GPS knop (kleiner en donkerder) */
    div[data-testid="column"] > div.stButton > button {
        background: #2D2D2D;
        color: white;
        box-shadow: none;
        border: 1px solid #444;
    }

    /* === ZOEKBALK === */
    /* Zwarte achtergrond dropdowns */
    div[data-baseweb="select"] > div {
        background-color: #2D2D2D !important;
        color: white !important;
        border-color: #444 !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="select"] span {
        color: #ddd !important;
    }
    ul[role="listbox"] {
        background-color: #2D2D2D !important;
    }
    ul[role="listbox"] li {
        color: #eee !important;
        border-bottom: 1px solid #444;
    }
    ul[role="listbox"] li[aria-selected="true"] {
        background-color: #3b82f6 !important;
    }

    /* === STATS BOX === */
    .stats-container {
        display: flex;
        justify-content: space-around;
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #333;
        margin-top: 15px;
        margin-bottom: 15px;
    }
    .stat-item { text-align: center; }
    .stat-value { font-size: 1.6rem; font-weight: 800; color: white; }
    .stat-label { font-size: 0.75rem; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }

</style>
""", unsafe_allow_html=True)

# --- 3. STATE ---
if "start_coords" not in st.session_state: st.session_state["start_coords"] = None
if "route_data" not in st.session_state: st.session_state["route_data"] = None
if "current_gps" not in st.session_state: st.session_state["current_gps"] = None
if "random_seed" not in st.session_state: st.session_state["random_seed"] = random.randint(1, 9999)
if "start_label" not in st.session_state: st.session_state["start_label"] = ""

# --- 4. GPS LOGIC ---
gps_data = get_geolocation()
if gps_data and 'coords' in gps_data:
    st.session_state["current_gps"] = [
        gps_data['coords']['latitude'],
        gps_data['coords']['longitude']
    ]
    # Eerste keer automatisch invullen
    if st.session_state["start_coords"] is None:
        st.session_state["start_coords"] = [gps_data['coords']['longitude'], gps_data['coords']['latitude']]
        st.session_state["start_label"] = "📍 Current Location"
        st.rerun()

# --- 5. UI LAYOUT ---

# HEADER
st.markdown("""
<div class="app-header">
    <div class="app-title">⚡ DRouted</div>
</div>
""", unsafe_allow_html=True)

# DE KAART
m_center = [52.1, 5.1]
zoom = 8

if st.session_state["current_gps"]:
    m_center = st.session_state["current_gps"]
    zoom = 13
if st.session_state["start_coords"]:
    m_center = [st.session_state["start_coords"][1], st.session_state["start_coords"][0]]
    zoom = 14

m = folium.Map(location=m_center, zoom_start=zoom, tiles="CartoDB positron", zoom_control=False)

if st.session_state["route_data"]:
    folium.GeoJson(
        st.session_state["route_data"],
        style_function=lambda x: {'color': '#8b5cf6', 'weight': 6, 'opacity': 0.8}
    ).add_to(m)
    bbox = st.session_state["route_data"]['bbox']
    m.fit_bounds([[bbox[1], bbox[0]], [bbox[3], bbox[2]]])

if st.session_state["start_coords"]:
    folium.Marker(
        [st.session_state["start_coords"][1], st.session_state["start_coords"][0]],
        icon=folium.Icon(color="green", icon="play", prefix="fa")
    ).add_to(m)

if st.session_state["current_gps"]:
    folium.CircleMarker(
        st.session_state["current_gps"], radius=10, color="#3b82f6", fill=True, fill_opacity=1, stroke=False
    ).add_to(m)

st_folium(m, width="100%", height=380)

# STATISTIEKEN (Alleen als er een route is)
if st.session_state["route_data"]:
    summary = st.session_state["route_data"]['features'][0]['properties']['summary']
    dist = round(summary['distance'] / 1000, 2)
    dur = int(summary['duration'] // 60)

    st.markdown(f"""
    <div class="stats-container">
        <div class="stat-item">
            <div class="stat-value">{dist} km</div>
            <div class="stat-label">Distance</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{dur} min</div>
            <div class="stat-label">Walking Time</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# BEDIENINGSPANEEL
st.write("")  # Spacer

# Rij 1: Locatie + GPS Knop
col1, col2 = st.columns([0.8, 0.2])
with col1:
    start_selection = st_searchbox(
        search_address,
        key="sb_start",
        placeholder="Start Location...",
        default=st.session_state.get("start_label", ""),
        clear_on_submit=False
    )
    if start_selection:
        st.session_state["start_coords"] = start_selection

with col2:
    # GPS Reset knop
    if st.button("📍", help="Use GPS"):
        st.session_state["start_coords"] = None  # Reset -> triggert auto-fill
        st.rerun()

# Rij 2: Slider
dist_km = st.slider("Loop Distance (km)", 2.0, 20.0, 5.0, 0.5)

# Rij 3: DE ACTIE KNOP
st.write("")
if st.button("🔄 GENERATE NEW LOOP"):
    # 1. Nieuwe random seed
    st.session_state["random_seed"] = random.randint(1, 100000)

    # 2. Check & Bereken
    if not st.session_state["start_coords"]:
        st.warning("Please verify start location.")
    else:
        with st.spinner("Finding best path..."):
            # Hardcoded 'foot-walking' -> Alleen wandelen!
            route = calculate_round_trip(
                st.session_state["start_coords"],
                dist_km,
                "foot-walking",
                seed=st.session_state["random_seed"]
            )

            if "error" in route:
                st.error(route['error'])
            else:
                st.session_state["route_data"] = route
                st.rerun()

# Rij 4: Export (Klein onderaan)
if st.session_state["route_data"]:
    gpx_data = convert_geojson_to_gpx(st.session_state["route_data"])
    if gpx_data:
        st.download_button("💾 Download GPX", gpx_data, "drouted_loop.gpx", "application/gpx+xml",
                           use_container_width=True)
