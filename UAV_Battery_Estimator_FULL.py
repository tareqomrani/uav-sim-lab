import streamlit as st
import time
import math
import pandas as pd
from datetime import datetime

# Constants
SIGMA = 5.670374419e-8
AIR_DENSITY_SEA_LEVEL = 1.225
GRAVITY = 9.81

# --- Physics Models ---

def compute_air_density(altitude_m):
    return AIR_DENSITY_SEA_LEVEL * (1 - 0.0000225577 * altitude_m) ** 5.25588

def calculate_drag_force(velocity_mps, Cd, frontal_area_m2, air_density):
    return 0.5 * air_density * Cd * frontal_area_m2 * velocity_mps**2

def calculate_lift_force(velocity_mps, Cl, wing_area_m2, air_density):
    return 0.5 * air_density * Cl * wing_area_m2 * velocity_mps**2

def estimate_propulsion_power_needed(drag_force, velocity_mps, prop_efficiency=0.7):
    return drag_force * velocity_mps / prop_efficiency

def estimate_hybrid_power_split(draw_watt, flight_mode="Cruise", hybrid_blend_ratio=0.2):
    if flight_mode == "Climb":
        return draw_watt * 0.4
    elif flight_mode == "Loiter":
        return draw_watt * 0.3
    else:
        return draw_watt * hybrid_blend_ratio

def estimate_thermal_signature_realistic(draw_watt, efficiency, surface_area, emissivity, ambient_temp_C, convective_factor=0.3):
    waste_heat = draw_watt * (1 - efficiency)
    if waste_heat <= 0 or surface_area <= 0 or emissivity <= 0:
        return 0
    adjusted_heat = waste_heat * (1 - convective_factor)
    temp_K = (adjusted_heat / (emissivity * SIGMA * surface_area)) ** 0.25
    temp_C = temp_K - 273.15
    delta_T = temp_C - ambient_temp_C
    return round(delta_T, 1)

def compute_battery_loss(battery_wh, draw_watt):
    if draw_watt < 200:
        return battery_wh * 0.9
    elif draw_watt < 500:
        return battery_wh * 0.85
    else:
        return battery_wh * 0.8

# --- UAV Profiles ---

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 150, "battery_wh": 60, "wing_area": 0.2, "frontal_area": 0.1, "Cd": 1.2, "Cl": 0.9, "ai_capabilities": "Basic flight stabilization, waypoint navigation"},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 120, "battery_wh": 68, "wing_area": 0.25, "frontal_area": 0.11, "Cd": 1.1, "Cl": 0.85, "ai_capabilities": "Visual object tracking, return-to-home, autonomous mapping"},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 90, "battery_wh": 50, "wing_area": 0.3, "frontal_area": 0.12, "Cd": 1.0, "Cl": 0.95, "ai_capabilities": "Auto-stabilized flight, limited route autonomy"},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 180, "battery_wh": 275, "wing_area": 0.4, "frontal_area": 0.2, "Cd": 1.0, "Cl": 0.95, "ai_capabilities": "AI-enhanced ISR mission planning, autonomous loitering"},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 650, "battery_wh": 150, "wing_area": 11.0, "frontal_area": 1.8, "Cd": 0.6, "Cl": 1.1, "ai_capabilities": "Semi-autonomous surveillance, pattern-of-life analysis"},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "wing_area": 16.0, "frontal_area": 2.5, "Cd": 0.55, "Cl": 1.15, "ai_capabilities": "Real-time threat detection, sensor fusion, autonomous target tracking"},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 90, "battery_wh": 45, "wing_area": 0.15, "frontal_area": 0.1, "Cd": 1.3, "Cl": 0.85, "ai_capabilities": "Full obstacle avoidance, visual SLAM, autonomous following"},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 400, "battery_wh": 710, "wing_area": 0.4, "frontal_area": 0.3, "Cd": 1.2, "Cl": 0.9, "ai_capabilities": "Autonomous camera coordination, precision loitering"},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Battery", "draw_watt": 220, "battery_wh": 100, "wing_area": 0.35, "frontal_area": 0.18, "Cd": 1.1, "Cl": 0.9, "ai_capabilities": "AI-driven ISR, edge-based visual classification, GPS-denied flight"},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 160, "battery_wh": 150, "wing_area": 0.5, "frontal_area": 0.2, "Cd": 1.0, "Cl": 1.0, "ai_capabilities": "Modular AI sensor pods, onboard geospatial intelligence, autonomous route learning"},
    "Custom Build": {"max_payload_g": 1500, "base_weight_kg": 2.0, "power_system": "Battery", "draw_watt": 180, "battery_wh": 150, "wing_area": 0.4, "frontal_area": 0.2, "Cd": 1.1, "Cl": 0.9, "ai_capabilities": "User-defined platform with configurable components"}
}

# --- Streamlit UI ---

st.set_page_config(page_title='Aerospace UAV Simulator', layout='centered')
st.markdown("<h1 style='color:#00FF00;'>Aerospace-Grade UAV Simulator</h1>", unsafe_allow_html=True)

drone_model = st.selectbox("Select UAV", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]
flight_mode = st.selectbox("Flight Mode", ["Hover", "Cruise", "Climb", "Loiter"])
airspeed_kmh = st.number_input("Flight Speed (km/h)", value=60.0, min_value=0.0)
altitude_m = st.number_input("Altitude (m)", value=500)
ambient_temp = st.number_input("Ambient Temp (°C)", value=25.0)

airspeed_mps = airspeed_kmh / 3.6
rho = compute_air_density(altitude_m)
drag_force = calculate_drag_force(airspeed_mps, profile["Cd"], profile["frontal_area"], rho)
lift_force = calculate_lift_force(airspeed_mps, profile["Cl"], profile["wing_area"], rho)
propulsion_power = estimate_propulsion_power_needed(drag_force, airspeed_mps)
usable_battery_wh = compute_battery_loss(profile["battery_wh"], propulsion_power)

battery_draw = estimate_hybrid_power_split(propulsion_power, flight_mode) if profile["power_system"] == "Hybrid" else propulsion_power
flight_time_minutes = (usable_battery_wh / battery_draw) * 60
delta_T = estimate_thermal_signature_realistic(draw_watt=propulsion_power, efficiency=0.85,
                                                surface_area=profile["frontal_area"], emissivity=0.9,
                                                ambient_temp_C=ambient_temp)

# --- Display Metrics ---
st.metric("Air Density (kg/m³)", f"{rho:.2f}")
st.metric("Lift Force (N)", f"{lift_force:.1f}")
st.metric("Drag Force (N)", f"{drag_force:.1f}")
st.metric("Power Needed (W)", f"{propulsion_power:.1f}")
st.metric("Battery Draw (W)", f"{battery_draw:.1f}")
st.metric("Usable Battery (Wh)", f"{usable_battery_wh:.1f}")
st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
st.metric("ΔT Thermal Signature", f"{delta_T:.1f}°C")

if delta_T > 15:
    st.warning("⚠️ High IR visibility risk.")
elif delta_T > 10:
    st.info("🟡 Moderate IR visibility.")
else:
    st.success("🟢 Low IR signature.")

# --- Export ---
def export_mission_log():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_data = {
        "UAV Model": drone_model,
        "Flight Mode": flight_mode,
        "Airspeed (km/h)": airspeed_kmh,
        "Altitude (m)": altitude_m,
        "Ambient Temp (°C)": ambient_temp,
        "Air Density (kg/m3)": rho,
        "Lift Force (N)": lift_force,
        "Drag Force (N)": drag_force,
        "Power Needed (W)": propulsion_power,
        "Battery Draw (W)": battery_draw,
        "Usable Battery (Wh)": usable_battery_wh,
        "Estimated Flight Time (min)": flight_time_minutes,
        "Thermal Signature ΔT (°C)": delta_T,
        "Timestamp": timestamp
    }
    df = pd.DataFrame([log_data])
    filename = f"uav_mission_log_{timestamp}.csv"
    df.to_csv(filename, index=False)
    return filename

if st.button("Export Mission Log"):
    log_file = export_mission_log()
    st.success(f"Mission log saved as `{log_file}`")
