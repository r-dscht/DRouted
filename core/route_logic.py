import openrouteservice
import streamlit as st
import random
from shapely.geometry import LineString
from shapely.ops import transform
from functools import partial
import pyproj


# --- 1. CONFIGURATIE ---
@st.cache_resource
def get_client():
    try:
        api_key = st.secrets["ors_key"]
        return openrouteservice.Client(key=api_key)
    except Exception:
        return None


# --- 2. ADRES ZOEKEN (AUTOCOMPLETE) ---
@st.cache_data(ttl=3600)
def search_address(search_term):
    if not search_term: return []
    client = get_client()
    if not client: return []
    try:
        results = client.pelias_search(text=search_term, size=6)
        suggestions = []
        for feat in results['features']:
            props = feat['properties']
            coords = feat['geometry']['coordinates']
            full_label = props.get('label', 'Unknown')
            parts = full_label.split(',')
            if len(parts) > 2:
                short_label = f"{parts[0].strip()}, {parts[1].strip()}"
            else:
                short_label = full_label
            suggestions.append((short_label, coords))
        return suggestions
    except Exception:
        return []


# --- 3. REVERSE GEOCODING ---
@st.cache_data(ttl=3600)
def reverse_geocode(lat, lng):
    client = get_client()
    if not client: return f"{lat:.4f}, {lng:.4f}"
    try:
        res = client.pelias_reverse(point=[lng, lat])
        if res['features']:
            label = res['features'][0]['properties']['label']
            parts = label.split(',')
            if len(parts) > 2:
                return f"{parts[0].strip()}, {parts[1].strip()}"
            return label
        return f"{lat:.4f}, {lng:.4f}"
    except:
        return f"{lat:.4f}, {lng:.4f}"


# --- 4. GPX CONVERTER (NIEUW) ---
def convert_geojson_to_gpx(route_data, name="DRouted Trip"):
    """Zet de GeoJSON data om naar een GPX string voor download."""
    try:
        coords = route_data['features'][0]['geometry']['coordinates']

        gpx_header = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="DRouted" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>{name}</name>
  </metadata>
  <trk>
    <name>{name}</name>
    <trkseg>"""

        gpx_points = ""
        for lon, lat in coords:
            # Let op: GeoJSON is Lon,Lat -> GPX wil lat="..." lon="..."
            gpx_points += f'\n      <trkpt lat="{lat}" lon="{lon}"></trkpt>'

        gpx_footer = """
    </trkseg>
  </trk>
</gpx>"""

        return gpx_header + gpx_points + gpx_footer
    except Exception as e:
        return None


# --- 5. NORMALE ROUTE ---
@st.cache_data(ttl=600, show_spinner=False)
def calculate_route(start_coords, end_coords, profile='driving-car'):
    client = get_client()
    if not client: return {"error": "API Client not available"}
    try:
        route = client.directions(
            coordinates=[start_coords, end_coords],
            profile=profile,
            format='geojson',
            geometry_simplify=True,
            instructions=True,
            language='en'
        )
        return route
    except Exception as e:
        return {"error": str(e)}


# --- 6. LUS GENERATOR (AANGEPAST) ---
class RouteLoopOptimiser:
    def __init__(self, api_key):
        self.client = openrouteservice.Client(key=api_key)
        self.project_to_meters = partial(
            pyproj.transform,
            pyproj.Proj('EPSG:4326'),
            pyproj.Proj('EPSG:3857')
        )

    def _calculate_overlap_ratio(self, coords):
        if not coords or len(coords) < 2: return 0.0
        try:
            line = LineString(coords)
            line_meters = transform(self.project_to_meters, line)
            total_length = line_meters.length
            if total_length == 0: return 0.0
            buffered_poly = line_meters.buffer(15.0)
            actual_area = buffered_poly.area
            theoretical_area = total_length * 30.0
            ratio = actual_area / theoretical_area
            return min(ratio, 1.0)
        except Exception:
            return 0.5

    def generate_optimized_loop(self, start_coords, target_dist_meters, num_candidates=3, profile='foot-walking',
                                seed_base=0):
        candidates = []
        seeds = set()
        random.seed(seed_base)

        # FIX: We verminderen de gevraagde afstand met 20% (factor 0.8)
        # Omdat wegen kronkelen, wordt de route anders bijna altijd te lang.
        adjusted_target = int(target_dist_meters * 0.8)

        while len(seeds) < num_candidates:
            seeds.add(random.randint(1, 10000))

        for seed in seeds:
            try:
                route_response = self.client.directions(
                    coordinates=[start_coords],
                    profile=profile,
                    format='geojson',
                    options={
                        "round_trip": {
                            "length": adjusted_target,  # We sturen de gecorrigeerde afstand
                            "points": 5,
                            "seed": seed
                        }
                    },
                    validate=False
                )
                feature = route_response['features'][0]
                geometry = feature['geometry']['coordinates']
                summary = feature['properties']['summary']
                actual_dist = summary['distance']

                # We vergelijken met de ORIGINELE target van de gebruiker
                dist_error = abs(actual_dist - target_dist_meters)
                dist_score = dist_error / target_dist_meters
                overlap_ratio = self._calculate_overlap_ratio(geometry)
                overlap_penalty = 1.0 - overlap_ratio

                final_score = (dist_score * 1.5) + (overlap_penalty * 2.0)

                candidates.append({
                    'final_score': final_score,
                    'route': route_response
                })
            except Exception:
                continue

        if not candidates:
            return {"error": "Could not generate loop. Try adjusting distance."}

        best_candidate = sorted(candidates, key=lambda x: x['final_score'])[0]
        return best_candidate['route']


# --- WRAPPER FUNCTIE ---
@st.cache_data(ttl=600, show_spinner=False)
def calculate_round_trip(start_coords, target_km, profile='foot-walking', seed=0):
    try:
        api_key = st.secrets["ors_key"]
        optimizer = RouteLoopOptimiser(api_key)
        target_meters = int(target_km * 1000)

        return optimizer.generate_optimized_loop(
            start_coords=start_coords,
            target_dist_meters=target_meters,
            num_candidates=3,
            profile=profile,
            seed_base=seed
        )
    except Exception as e:
        return {"error": str(e)}


# Functie om de convertor beschikbaar te maken voor app.py
def get_gpx_converter():
    return convert_geojson_to_gpx