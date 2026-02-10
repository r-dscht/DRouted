import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_searchbox import st_searchbox
from streamlit_js_eval import get_geolocation
import time
import random

# Importeer ook de nieuwe gpx functie
from core.route_logic import search_address, calculate_route, reverse_geocode, calculate_round_trip, \
    convert_geojson_to_gpx

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(
    page_title="DRouted",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Algemene witruimte optimalisatie voor mobiel */
    .block-container { 
        padding-top: 1rem; 
        padding-bottom: 2rem; 
        padding-left: 1rem;
        padding-right: 1rem;
    }

    /* === DASHBOARD CARDS (RESPONSIVE) === */
    .metric-container {
        display: flex;
        justify-content: center;
        gap: 20px;
        margin-bottom: 20px;
        flex-wrap: wrap; /* Belangrijk: hierdoor gaan ze onder elkaar als het niet past */
    }

    .metric-card {
        background: #1E1E1E;
        border-radius: 12px;
        padding: 15px;
        width: 300px; /* Standaard breedte voor PC */
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        text-align: center;
        border: 1px solid #333;
    }

    /* === MOBIELE AANPASSINGEN === */
    /* Als scherm kleiner is dan 700px (Telefoons) */
    @media (max-width: 700px) {
        .metric-card {
            width: 100% !important; /* Gebruik volledige breedte van scherm */
            margin-bottom: 10px;
        }
        .metric-container {
            gap: 10px;
            flex-direction: column; /* Forceer onder elkaar */
        }
        /* Maak de titel in zijbalk iets kleiner op mobiel */
        h1 { font-size: 1.8rem !important; }
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-label {
        color: #bbb;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-icon { font-size: 1.5rem; display: block; margin-bottom: 5px; }

    /* Fix dropdowns op mobiel */
    div[data-baseweb="select"] span {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 200px; /* Iets smaller voor mobiel */
    }

    /* Zwarte achtergrond dropdowns */
    div[data-baseweb="select"] > div {
        background-color: #262730 !important;
        color: white !important;
        border-color: #4b4b4b !important;
    }
    ul[role="listbox"] li {
        color: white !important;
        background-color: #262730 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. SESSION STATE ---
if "start_coords" not in st.session_state: st.session_state["start_coords"] = None
if "end_coords" not in st.session_state: st.session_state["end_coords"] = None
if "route_data" not in st.session_state: st.session_state["route_data"] = None
if "current_gps" not in st.session_state: st.session_state["current_gps"] = None
if "random_seed" not in st.session_state: st.session_state["random_seed"] = 1

# --- 3. SIDEBAR CONTROLS ---
with st.sidebar:
    st.markdown("""
        <div style="text-align: left; margin-bottom: 10px;">
            <h1 style="margin: 0; font-size: 2.2rem; font-family: sans-serif; background: -webkit-linear-gradient(45deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                ⚡ DRouted
            </h1>
            <p style="margin: 0; color: #888; font-size: 0.8rem; letter-spacing: 1px;">MOBILE NAV</p>
        </div>
    """, unsafe_allow_html=True)

    # GPS Logic
    gps_data = get_geolocation()
    if gps_data and 'coords' in gps_data:
        st.session_state["current_gps"] = [
            gps_data['coords']['latitude'],
            gps_data['coords']['longitude']
        ]

    if st.button("📍 Use my location", use_container_width=True):
        if st.session_state["current_gps"]:
            lat, lng = st.session_state["current_gps"]
            st.session_state["start_coords"] = [lng, lat]
            st.session_state["start_label"] = "📍 Current Location"
            st.success("Located!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.warning("GPS searching...")

    st.markdown("---")

    route_type = st.radio("Mode:", ["Destination 🏁", "Loop 🔄"])

    start_selection = st_searchbox(
        search_address,
        key="sb_start",
        label="Start",
        placeholder="Start address...",
        default=st.session_state.get("start_label", ""),
        clear_on_submit=False
    )
    if start_selection:
        st.session_state["start_coords"] = start_selection

    if route_type == "Destination 🏁":
        end_selection = st_searchbox(
            search_address,
            key="sb_end",
            label="End",
            placeholder="Destination...",
            default=st.session_state.get("end_label", ""),
            clear_on_submit=False
        )
        if end_selection:
            st.session_state["end_coords"] = end_selection

    else:
        target_km = st.slider("Distance (km)", 1.0, 20.0, 5.0, 0.5)
        if st.button("🔀 Shuffle", use_container_width=True):
            st.session_state["random_seed"] = random.randint(1, 10000)
            st.toast("Shuffling...")

    profile_map = {"Car 🚗": "driving-car", "Bike 🚲": "cycling-regular", "Walk 🚶": "foot-walking"}
    transport_mode = st.radio("Transport", options=profile_map.keys())

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 GO", type="primary", use_container_width=True):
            if not st.session_state["start_coords"]:
                st.warning("Start required")
            else:
                with st.spinner("Routing..."):
                    if route_type == "Destination 🏁":
                        if st.session_state["end_coords"]:
                            route = calculate_route(st.session_state["start_coords"], st.session_state["end_coords"],
                                                    profile_map[transport_mode])
                        else:
                            route = {"error": "No destination"}
                    else:
                        route = calculate_round_trip(st.session_state["start_coords"], target_km,
                                                     profile_map[transport_mode], seed=st.session_state["random_seed"])

                    if "error" in route:
                        st.error(f"Error: {route['error']}")
                    else:
                        st.session_state["route_data"] = route

    with col2:
        if st.button("❌ Clear", use_container_width=True):
            st.session_state["route_data"] = None
            st.session_state["start_coords"] = None
            st.session_state["end_coords"] = None
            st.session_state["start_label"] = ""
            st.session_state["end_label"] = ""
            st.rerun()

    if st.session_state["route_data"]:
        st.markdown("---")
        gpx_data = convert_geojson_to_gpx(st.session_state["route_data"])
        if gpx_data:
            st.download_button("💾 Save GPX", gpx_data, "route.gpx", "application/gpx+xml", use_container_width=True)

# --- 4. DASHBOARD & MAP ---

if st.session_state["route_data"]:
    summary = st.session_state["route_data"]['features'][0]['properties']['summary']
    dist_km = round(summary['distance'] / 1000, 2)
    dur_seconds = summary['duration']

    if dur_seconds < 3600:
        time_str = f"{int(dur_seconds // 60)} min"
    else:
        time_str = f"{int(dur_seconds // 3600)}h {int((dur_seconds % 3600) / 60)}m"

    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-card">
            <span class="metric-icon">⏱️</span>
            <div class="metric-label">Duration</div>
            <div class="metric-value">{time_str}</div>
        </div>
        <div class="metric-card">
            <span class="metric-icon">📏</span>
            <div class="metric-label">Distance</div>
            <div class="metric-value">{dist_km} km</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Mobiele kaart: Iets minder hoog zodat je niet eindeloos hoeft te scrollen
map_height = 450

m_center = [52.1, 5.1]
zoom = 7

if st.session_state["current_gps"]:
    m_center = st.session_state["current_gps"]
    zoom = 12

if st.session_state["start_coords"]:
    m_center = [st.session_state["start_coords"][1], st.session_state["start_coords"][0]]
    zoom = 14

m = folium.Map(location=m_center, zoom_start=zoom, tiles="CartoDB positron")

if st.session_state["current_gps"]:
    folium.CircleMarker(st.session_state["current_gps"], radius=8, color="#2A81CB", fill=True, fill_color="#2A81CB",
                        fill_opacity=1).add_to(m)

if st.session_state["route_data"]:
    route_color = "#3b82f6"
    if "Bike" in transport_mode: route_color = "#2ecc71"
    if "Walk" in transport_mode: route_color = "#e67e22"

    folium.GeoJson(st.session_state["route_data"],
                   style_function=lambda x: {'color': route_color, 'weight': 5, 'opacity': 0.8}).add_to(m)
    bbox = st.session_state["route_data"]['bbox']
    m.fit_bounds([[bbox[1], bbox[0]], [bbox[3], bbox[2]]])

if st.session_state["start_coords"]:
    folium.Marker([st.session_state["start_coords"][1], st.session_state["start_coords"][0]],
                  icon=folium.Icon(color="green", icon="play", prefix="fa")).add_to(m)

if st.session_state["end_coords"]:
    folium.Marker([st.session_state["end_coords"][1], st.session_state["end_coords"][0]],
                  icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)

map_output = st_folium(m, width="100%", height=map_height)

if map_output['last_clicked'] and route_type == "Destination 🏁":
    lat = map_output['last_clicked']['lat']
    lng = map_output['last_clicked']['lng']
    st.session_state["end_coords"] = [lng, lat]
    address_text = reverse_geocode(lat, lng)
    st.session_state["end_label"] = f"📍 {address_text}"
    st.toast("Destination set!")
    time.sleep(0.1)
    st.rerun()