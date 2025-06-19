
import streamlit as st
import time
import math
from fpdf import FPDF
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import io

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 150, "battery_wh": 60, "crash_risk": False, "ai_capabilities": "Basic flight stabilization, waypoint navigation", "default_payload_g": 400, "default_speed_kmh": 25, "default_altitude_m": 50, "default_wind_kmh": 8, "default_temp_c": 25, "default_surface_area_m2": 0.6},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 120, "battery_wh": 68, "crash_risk": False, "ai_capabilities": "Visual object tracking, return-to-home, autonomous mapping", "default_payload_g": 250, "default_speed_kmh": 36, "default_altitude_m": 100, "default_wind_kmh": 10, "default_temp_c": 25, "default_surface_area_m2": 0.5},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 90, "battery_wh": 50, "crash_risk": False, "ai_capabilities": "Auto-stabilized flight, limited route autonomy", "default_payload_g": 0, "default_speed_kmh": 45, "default_altitude_m": 150, "default_wind_kmh": 8, "default_temp_c": 22, "default_surface_area_m2": 0.75},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 180, "battery_wh": 275, "crash_risk": False, "ai_capabilities": "AI-enhanced ISR mission planning, autonomous loitering", "default_payload_g": 300, "default_speed_kmh": 65, "default_altitude_m": 200, "default_wind_kmh": 12, "default_temp_c": 20, "default_surface_area_m2": 1.2},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 650, "battery_wh": 150, "crash_risk": True, "ai_capabilities": "Semi-autonomous surveillance, pattern-of-life analysis", "default_payload_g": 100000, "default_speed_kmh": 215, "default_altitude_m": 1000, "default_wind_kmh": 18, "default_temp_c": 17, "default_surface_area_m2": 100},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "crash_risk": True, "ai_capabilities": "Real-time threat detection, sensor fusion, autonomous target tracking", "default_payload_g": 800000, "default_speed_kmh": 280, "default_altitude_m": 1200, "default_wind_kmh": 20, "default_temp_c": 18, "default_surface_area_m2": 310},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 90, "battery_wh": 45, "crash_risk": False, "ai_capabilities": "Full obstacle avoidance, visual SLAM, autonomous following", "default_payload_g": 75, "default_speed_kmh": 30, "default_altitude_m": 80, "default_wind_kmh": 10, "default_temp_c": 24, "default_surface_area_m2": 0.4},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 400, "battery_wh": 710, "crash_risk": False, "ai_capabilities": "Autonomous camera coordination, precision loitering", "default_payload_g": 4500, "default_speed_kmh": 35, "default_altitude_m": 120, "default_wind_kmh": 12, "default_temp_c": 23, "default_surface_area_m2": 1.5},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Battery", "draw_watt": 220, "battery_wh": 100, "crash_risk": True, "ai_capabilities": "AI-driven ISR, edge-based visual classification, GPS-denied flight", "default_payload_g": 1000, "default_speed_kmh": 55, "default_altitude_m": 180, "default_wind_kmh": 10, "default_temp_c": 21, "default_surface_area_m2": 1.0},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 160, "battery_wh": 150, "crash_risk": False, "ai_capabilities": "Modular AI sensor pods, onboard geospatial intelligence, autonomous route learning", "default_payload_g": 800, "default_speed_kmh": 60, "default_altitude_m": 200, "default_wind_kmh": 9, "default_temp_c": 20, "default_surface_area_m2": 1.3},
    "Custom Build": {"max_payload_g": 1500, "base_weight_kg": 2.0, "power_system": "Battery", "draw_watt": 180, "battery_wh": 150, "crash_risk": False, "ai_capabilities": "User-defined platform with configurable components", "default_payload_g": 750, "default_speed_kmh": 40, "default_altitude_m": 100, "default_wind_kmh": 10, "default_temp_c": 25, "default_surface_area_m2": 1.0}
}


def estimate_thermal_signature(draw_watt, efficiency, surface_area, emissivity, ambient_temp_C):
    sigma = 5.670374419e-8  # Stefan–Boltzmann constant
    waste_heat = draw_watt * (1 - efficiency)
    if waste_heat <= 0 or surface_area <= 0 or emissivity <= 0:
        return 0
    temp_K = (waste_heat / (emissivity * sigma * surface_area)) ** 0.25
    temp_C = temp_K - 273.15
    return round(temp_C - ambient_temp_C, 1)

def cap_flight_time_range(model_name, time_min, distance_km):
    caps = {
        "Generic Quad": (30, 6), "DJI Phantom": (45, 10), "RQ-11 Raven": (90, 15),
        "RQ-20 Puma": (120, 20), "MQ-1 Predator": (1200, 1000), "MQ-9 Reaper": (1500, 1200),
        "Skydio 2+": (30, 5), "Freefly Alta 8": (35, 8), "Teal Golden Eagle": (50, 10),
        "Quantum Systems Vector": (120, 25), "Custom Build": (999, 999)
    }
    cap_time, cap_range = caps.get(model_name, (60, 10))
    return min(time_min, cap_time), min(distance_km, cap_range)

def create_pdf_report(profile, payload_g, flight_time_min, distance_km, temp_C, delta_T, risk, fuel_L=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    def add_line(label, value): pdf.cell(200, 10, txt=f"{label}: {value}", ln=True)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="UAV Mission Report", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    add_line("UAV Model", profile)
    add_line("Payload", f"{payload_g} g")
    add_line("Flight Time", f"{flight_time_min:.1f} minutes")
    add_line("Max Range", f"{distance_km:.2f} km")
    add_line("Ambient Temperature", f"{temp_C} °C")
    add_line("Thermal Signature ΔT", f"{delta_T:.1f} °C")
    add_line("Thermal Risk", risk)
    if fuel_L is not None: add_line("Estimated Fuel Used", f"{fuel_L:.2f} L")
    buffer = io.BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

def thermal_risk_rating(delta_T):
    if delta_T < 10: return "Low"
    elif delta_T < 20: return "Moderate"
    else: return "High"

st.set_page_config(page_title='UAV Route Planner & Mission Report', layout='centered')
st.title("🛰️ UAV Route Planner & Mission Report Generator")

st.subheader("📍 Route Planner")
m = folium.Map(location=[30.0, 0.0], zoom_start=2)
m.add_child(folium.LatLngPopup())
map_data = st_folium(m, height=400, returned_objects=["last_clicked"])

if map_data.get("last_clicked"):
    lat, lon = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    if "route_points" not in st.session_state:
        st.session_state["route_points"] = []
    st.session_state["route_points"].append((lat, lon))

total_km = 0
if st.session_state.get("route_points"):
    for i, pt in enumerate(st.session_state["route_points"]):
        folium.Marker(pt, tooltip=f"Waypoint {i+1}").add_to(m)
    folium.PolyLine(st.session_state["route_points"], color="blue").add_to(m)
    st_folium(m, height=400, key="updated_map")

    total_km = sum(
        geodesic(st.session_state["route_points"][i], st.session_state["route_points"][i+1]).km
        for i in range(len(st.session_state["route_points"]) - 1)
    )
    st.metric("Planned Route Distance", f"{total_km:.2f} km")
    if st.button("Clear Route"):
        del st.session_state["route_points"]

st.subheader("📊 Mission Configuration")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]
payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, value=profile["default_payload_g"])
temperature_c = st.number_input("Ambient Temperature (°C)", value=profile["default_temp_c"])

surface_area = profile.get("default_surface_area_m2", 0.3)
delta_T = estimate_thermal_signature(
    draw_watt=profile["draw_watt"], efficiency=0.85,
    surface_area=surface_area,
    emissivity=0.9, ambient_temp_C=temperature_c
)

delta_T = st.slider("Thermal ΔT", 0.0, 50.0, delta_T)
flight_time_min = st.slider("Flight Time Estimate (min)", 5, 1800, 45)
fuel_L = st.slider("Fuel Estimate (L)", 0.0, 500.0, 10.0) if profile["power_system"] == "Hybrid" else None

flight_time_capped, distance_capped = cap_flight_time_range(drone_model, flight_time_min, total_km)
risk = thermal_risk_rating(delta_T)

if st.button("📄 Download Mission Report"):
    buffer = create_pdf_report(
        profile=drone_model,
        payload_g=payload_weight_g,
        flight_time_min=flight_time_capped,
        distance_km=distance_capped,
        temp_C=temperature_c,
        delta_T=delta_T,
        risk=risk,
        fuel_L=fuel_L
    )
    st.download_button("Download PDF", data=buffer, file_name=f"{drone_model}_MissionReport.pdf", mime="application/pdf")


# 🔍 AI Suggestions
st.subheader("💡 AI Suggestions")
if payload_weight_g == profile["max_payload_g"]:
    st.write("• Payload is at maximum capacity.")
if temperature_c > 35 or temperature_c < 5:
    st.write("• Extreme temps may degrade battery performance.")
if fuel_L and fuel_L > 200:
    st.write("• Fuel usage is high — optimize hybrid usage or flight time.")
if delta_T > 20:
    st.write("• High thermal signature. Consider altitude or stealth tuning.")
if total_km > 20 and profile["power_system"] == "Battery":
    st.write("• Route may exceed battery UAV's endurance.")
if profile["power_system"] == "Battery" and profile["battery_wh"] < 30:
    st.write("• Battery capacity under 30 Wh. May limit range severely.")

# 🔋 Battery Simulation
st.subheader("🔋 Live Battery Simulation")

battery_wh = profile["battery_wh"]
draw_watt = profile["draw_watt"]
draw_per_sec = draw_watt / 3600
total_seconds = int((battery_wh / draw_per_sec))
time_step = 5
steps = total_seconds // time_step

progress = st.progress(0)
status = st.empty()
gauge = st.empty()
timer = st.empty()

for i in range(steps + 1):
    battery_used = i * time_step * draw_per_sec
    battery_remaining = max(0, battery_wh - battery_used)
    pct = max(0, (battery_remaining / battery_wh) * 100)
    bars = int(pct // 10)
    gauge.markdown(f"**Battery Gauge:** `[{'|'*bars}{' '*(10-bars)}] {pct:.0f}%`")
    status.markdown(f"**Remaining:** {battery_remaining:.1f} Wh **Power Draw:** {draw_watt:.0f} W")
    timer.markdown(f"**Elapsed:** {i * time_step} sec **Remaining:** {max(0, total_seconds - i*time_step)} sec")
    progress.progress(i / steps)
    time.sleep(0.02)


st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")

st.subheader("📡 Signature Detection Analysis")
show_ir_radius = st.checkbox("Visualize IR Detection Radius")
include_rcs_estimate = st.checkbox("Include Radar Cross-Section Estimate")

if include_rcs_estimate:
    def radar_detectability(rcs_m2):
        if rcs_m2 < 0.01:
            return "Low"
        elif rcs_m2 < 0.1:
            return "Moderate"
        else:
            return "High"

    rcs = profile.get("rcs_m2", 0.1)
    radar_risk = radar_detectability(rcs)
    st.metric("Radar Detectability", radar_risk)

if show_ir_radius and st.session_state.get("route_points"):
    def estimate_ir_detection_radius(delta_T, surface_area):
        return min(20, 0.2 * delta_T * math.sqrt(surface_area))  # in km

    radius_km = estimate_ir_detection_radius(delta_T, surface_area)
    center = st.session_state["route_points"][-1]
    m = folium.Map(location=center, zoom_start=12)
    for i, pt in enumerate(st.session_state["route_points"]):
        folium.Marker(pt, tooltip=f"Waypoint {i+1}").add_to(m)
    folium.PolyLine(st.session_state["route_points"], color="blue").add_to(m)
    folium.Circle(
        location=center,
        radius=radius_km * 1000,
        color="red",
        fill=True,
        fill_opacity=0.2,
        tooltip=f"IR Detection Radius: {radius_km:.2f} km"
    ).add_to(m)
    st_folium(m, height=400, key="map_with_ir_radius")



    import random
    import requests

st.subheader("🌍 Terrain & Threat Analysis")

# --- Terrain Elevation Simulation (stub) ---
simulate_terrain = st.checkbox("Enable Terrain Elevation Penalty (simulated)")
elevation_gain_m = 0
elevation_loss_m = 0

if simulate_terrain and st.session_state.get("route_points") and len(st.session_state["route_points"]) > 1:
    elevation_gain_m = random.randint(20, 200)
    elevation_loss_m = random.randint(10, 150)
    terrain_penalty_factor = 1.0 + elevation_gain_m * 0.0005
    st.markdown(f"**Simulated Elevation Gain:** {elevation_gain_m} m")
    st.markdown(f"**Simulated Elevation Loss:** {elevation_loss_m} m")
    st.markdown(f"**Energy Draw Penalty Factor:** x{terrain_penalty_factor:.2f}")
else:
    terrain_penalty_factor = 1.0

# --- Threat Zones ---
st.subheader("🛑 Threat Zones (Demo)")
threat_zones = {
    "IR Net Zone": {"lat": 30.25, "lon": 0.25, "radius_km": 10},
    "Radar Tower Alpha": {"lat": 30.15, "lon": 0.15, "radius_km": 8}
}
enabled_threats = st.multiselect("Enable Threat Zones", list(threat_zones.keys()))
threat_score = 0
zone_hits = []

if st.session_state.get("route_points"):
    for name in enabled_threats:
        zone = threat_zones[name]
        threat_loc = (zone["lat"], zone["lon"])
        for pt in st.session_state["route_points"]:
            dist = geodesic(threat_loc, pt).km
            if dist <= zone["radius_km"]:
                zone_hits.append(name)
                threat_score += 10
                break

    if zone_hits:
        st.warning(f"⚠️ Route intersects: {', '.join(set(zone_hits))}")
        st.metric("Threat Exposure Score", threat_score)
    else:
        st.success("✅ Route avoids all defined threat zones.")

    if show_ir_radius:
        for name in enabled_threats:
            zone = threat_zones[name]
            folium.Circle(
                location=(zone["lat"], zone["lon"]),
                radius=zone["radius_km"] * 1000,
                color="orange",
                fill=True,
                fill_opacity=0.2,
                tooltip=f"{name} ({zone['radius_km']} km)"
            ).add_to(m)
    threat_zones = {
        "IR Net Zone": {"lat": 30.25, "lon": 0.25, "radius_km": 10},
        "Radar Tower Alpha": {"lat": 30.15, "lon": 0.15, "radius_km": 8}
    }
    enabled_threats = st.multiselect("Enable Threat Zones", list(threat_zones.keys()))

    threat_score = 0
    zone_hits = []

    if st.session_state.get("route_points"):
        for name in enabled_threats:
            zone = threat_zones[name]
            threat_loc = (zone["lat"], zone["lon"])
            for pt in st.session_state["route_points"]:
                dist = geodesic(threat_loc, pt).km
                if dist <= zone["radius_km"]:
                    zone_hits.append(name)
                    threat_score += 10
                    break

        if zone_hits:
            st.warning(f"⚠️ Route intersects: {', '.join(set(zone_hits))}")
            st.metric("Threat Exposure Score", threat_score)
        else:
            st.success("✅ Route avoids all defined threat zones.")

        # Add circles to map if IR visualization was toggled earlier
        if show_ir_radius:
            for name in enabled_threats:
                zone = threat_zones[name]
                folium.Circle(
                    location=(zone["lat"], zone["lon"]),
                    radius=zone["radius_km"] * 1000,
                    color="orange",
                    fill=True,
                    fill_opacity=0.2,
                    tooltip=f"{name} ({zone['radius_km']} km)"
                ).add_to(m)


import pandas as pd

# === Terrain Elevation with Real API ===
st.subheader("🌐 Real Elevation Data (Optional)")
use_real_elevation = st.checkbox("Use Real Elevation API (OpenTopoData)")

def get_elevation(lat, lon):
    url = f"https://api.opentopodata.org/v1/eudem25m?locations={lat},{lon}"
    try:
        response = requests.get(url)
        data = response.json()
        return data["results"][0]["elevation"]
    except:
        return None

elevation_gain_m = 0
if use_real_elevation and st.session_state.get("route_points") and len(st.session_state["route_points"]) > 1:
    route_points = st.session_state["route_points"]
    elevations = [get_elevation(lat, lon) for lat, lon in route_points]
    elevations = [e for e in elevations if e is not None]
    if len(elevations) == len(route_points):
        elevation_gain_m = sum(max(e2 - e1, 0) for e1, e2 in zip(elevations, elevations[1:]))
        elevation_loss_m = sum(max(e1 - e2, 0) for e1, e2 in zip(elevations, elevations[1:]))
        terrain_penalty_factor = 1.0 + elevation_gain_m * 0.0005
        st.markdown(f"**Elevation Gain (API):** {elevation_gain_m:.1f} m")
        st.markdown(f"**Elevation Loss (API):** {elevation_loss_m:.1f} m")
        st.markdown(f"**Adjusted Terrain Penalty Factor:** x{terrain_penalty_factor:.2f}")
    else:
        st.warning("Some elevation data could not be retrieved. Falling back to default.")
        terrain_penalty_factor = 1.0
# === Upload Threat Zones ===
st.subheader("📂 User-Defined Threat Zones")
upload_threats = st.checkbox("Upload Custom Threat Zones (.csv)")

custom_threats = []
if upload_threats:
    uploaded_file = st.file_uploader("Upload Threat Zones CSV", type=["csv"])
    if uploaded_file:
        df_zones = pd.read_csv(uploaded_file)
        for _, row in df_zones.iterrows():
            folium.Circle(
                location=(row["lat"], row["lon"]),
                radius=row["radius_km"] * 1000,
                color="red" if row["type"] == "ir" else "blue",
                tooltip=f"{row['name']} ({row['type']})"
            ).add_to(m)
            custom_threats.append({
                "name": row["name"],
                "lat": row["lat"],
                "lon": row["lon"],
                "radius_km": row["radius_km"],
                "type": row["type"]
            })

# === AI Recommendations ===
st.subheader("🧠 AI Mission Recommendations")
show_ai_tips = st.checkbox("Enable Flight Recommendations")

if show_ai_tips:
    st.markdown("### ✈️ Flight Optimization Suggestions")
    if payload_weight_g == profile["max_payload_g"]:
        st.write("• Payload is at maximum capacity.")
    if temperature_c > 35 or temperature_c < 5:
        st.write("• Extreme temps may degrade battery performance.")
    if fuel_L and fuel_L > 200:
        st.write("• Fuel usage is high — optimize hybrid usage or flight time.")
    if delta_T > 20:
        st.write("• High thermal signature. Consider lower altitude or stealth tuning.")
    if total_km > 20 and profile["power_system"] == "Battery":
        st.write("• Route may exceed battery UAV's endurance.")
    if elevation_gain_m > 150:
        st.write("• High elevation gain — consider flatter route to conserve energy.")
    if threat_score > 20:
        st.write("• Route crosses multiple threat zones — consider re-routing.")

