import openrouteservice
import streamlit as st
import random
from shapely.geometry import LineString
from shapely.ops import transform
from functools import partial
import pyproj


@st.cache_resource
def get_client():
    try:
        return openrouteservice.Client(key=st.secrets["ors_key"])
    except:
        return None


@st.cache_data(ttl=3600)
def search_address(search_term):
    if not search_term: return []
    client = get_client()
    if not client: return []
    try:
        results = client.pelias_search(text=search_term, size=5)
        suggestions = []
        for feat in results['features']:
            props = feat['properties']
            label = props.get('label', 'Unknown').split(',')
            # Pak eerste 2 delen of alles als het kort is
            short_label = ", ".join(label[:2]) if len(label) > 2 else ", ".join(label)
            suggestions.append((short_label, feat['geometry']['coordinates']))
        return suggestions
    except:
        return []


# DEZE FUNCTIE IS AANGEPAST: Profile parameter is weggehaald
@st.cache_data(ttl=600, show_spinner=False)
def calculate_round_trip(start_coords, target_km, profile_fixed, seed):
    try:
        api_key = st.secrets["ors_key"]
        optimizer = RouteLoopOptimiser(api_key)
        # Het profiel wordt nu doorgegeven vanuit app.py (die altijd 'foot-walking' stuurt)
        return optimizer.generate_optimized_loop(start_coords, int(target_km * 1000), 3, profile_fixed, seed)
    except Exception as e:
        return {"error": str(e)}


def convert_geojson_to_gpx(route_data):
    try:
        coords = route_data['features'][0]['geometry']['coordinates']
        pts = "".join([f'\n      <trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon, lat in coords])
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="DRouted">\n  <trk>\n    <name>DRouted Loop</name>\n    <trkseg>{pts}\n    </trkseg>\n  </trk>\n</gpx>'
    except:
        return None


class RouteLoopOptimiser:
    def __init__(self, api_key):
        self.client = openrouteservice.Client(key=api_key)
        self.proj = partial(pyproj.transform, pyproj.Proj('EPSG:4326'), pyproj.Proj('EPSG:3857'))

    def _calculate_overlap_ratio(self, coords):
        if not coords or len(coords) < 2: return 0.0
        try:
            line = LineString(coords)
            line_m = transform(self.proj, line)
            if line_m.length == 0: return 0.0
            return min(line_m.buffer(15.0).area / (line_m.length * 30.0), 1.0)
        except:
            return 0.5

    def generate_optimized_loop(self, start, target_m, candidates, profile, seed_base):
        best = None
        target_adj = int(target_m * 0.8)
        random.seed(seed_base)
        seeds = {random.randint(1, 99999) for _ in range(candidates)}

        for seed in seeds:
            try:
                res = self.client.directions(
                    coordinates=[start], profile=profile, format='geojson',
                    options={"round_trip": {"length": target_adj, "points": 5, "seed": seed}},
                    validate=False
                )
                summary = res['features'][0]['properties']['summary']
                geo = res['features'][0]['geometry']['coordinates']

                dist_score = abs(summary['distance'] - target_m) / target_m
                overlap_pen = 1.0 - self._calculate_overlap_ratio(geo)
                final_score = (dist_score * 1.5) + (overlap_pen * 2.0)

                if best is None or final_score < best['score']:
                    best = {'score': final_score, 'route': res}
            except:
                continue

        return best['route'] if best else {"error": "Could not generate a good loop here. Try adjusting distance."}
