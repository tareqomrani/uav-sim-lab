
import streamlit as st
import time
import math
import pandas as pd
from datetime import datetime

# Constants
SIGMA = 5.670374419e-8
AIR_DENSITY_SEA_LEVEL = 1.225
GRAVITY = 9.81

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

def estimate_thermal_signature(draw_watt, efficiency, surface_area, emissivity, ambient_temp_C):
    waste_heat = draw_watt * (1 - efficiency)
    if waste_heat <= 0 or surface_area <= 0 or emissivity <= 0:
        return 0
    temp_K = (waste_heat / (emissivity * SIGMA * surface_area)) ** 0.25
    temp_C = temp_K - 273.15
    delta_T = temp_C - ambient_temp_C
    return round(delta_T, 1)

def thermal_risk_rating(delta_T):
    if delta_T < 10:
        return "Low"
    elif delta_T < 20:
        return "Moderate"
    else:
        return "High"

def calculate_fuel_consumption(power_draw_watt, duration_hr, fuel_burn_rate_lph=1.5):
    return fuel_burn_rate_lph * duration_hr if power_draw_watt > 0 else 0

def compute_battery_loss(battery_wh, draw_watt):
    if draw_watt < 200:
        return battery_wh * 0.9
    elif draw_watt < 500:
        return battery_wh * 0.85
    else:
        return battery_wh * 0.8

def insert_thermal_and_fuel_outputs(total_draw, profile, flight_time_minutes, temperature_c, ir_shielding, delta_T):
    st.subheader("Thermal Signature & Fuel Analysis")
    risk = thermal_risk_rating(delta_T)
    st.metric(label="Thermal Signature Risk", value=f"{risk} (ΔT = {delta_T:.1f}°C)")
    if profile["power_system"].lower() == "hybrid":
        fuel_burned = calculate_fuel_consumption(
            power_draw_watt=total_draw,
            duration_hr=flight_time_minutes / 60
        )
        st.metric(label="Estimated Fuel Used", value=f"{fuel_burned:.2f} L")
    else:
        st.info("Fuel tracking not applicable for battery-powered UAVs.")



st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')
st.markdown("<h1 style='color:#00FF00;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)
st.caption("GPT-UAV Planner | Aerospace-Grade Upgrade | 2025")

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
},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "wing_area": 16.0, "frontal_area": 2.5, "Cd": 0.55, "Cl": 1.15, "ai_capabilities": "Real-time threat detection, sensor fusion, autonomous target tracking"},
    "Custom Build": {"max_payload_g": 1500, "base_weight_kg": 2.0, "power_system": "Battery", "draw_watt": 180, "battery_wh": 150, "wing_area": 0.4, "frontal_area": 0.2, "Cd": 1.1, "Cl": 0.9, "ai_capabilities": "User-defined platform"}
}

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

airspeed_kmh = st.slider("Flight Speed (km/h)", 10, 300, 80)
altitude_m = st.slider("Flight Altitude (m)", 0, 10000, 1000)
ambient_temp = st.number_input("Ambient Temperature (°C)", value=25.0)
flight_mode = st.selectbox("Flight Mode", ["Cruise", "Climb", "Loiter"])
payload_grams = st.slider("Payload (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5))

airspeed_mps = airspeed_kmh / 3.6
rho = compute_air_density(altitude_m)
drag_force = calculate_drag_force(airspeed_mps, profile["Cd"], profile["frontal_area"], rho)
lift_force = calculate_lift_force(airspeed_mps, profile["Cl"], profile["wing_area"], rho)
propulsion_power = estimate_propulsion_power_needed(drag_force, airspeed_mps)

usable_battery_wh = compute_battery_loss(profile["battery_wh"], propulsion_power)

if profile["power_system"].lower() == "hybrid":
    battery_draw = estimate_hybrid_power_split(propulsion_power, flight_mode)
else:
    battery_draw = propulsion_power

flight_time_minutes = (usable_battery_wh / battery_draw) * 60
delta_T = estimate_thermal_signature(draw_watt=propulsion_power, efficiency=0.85, surface_area=profile["frontal_area"], emissivity=0.9, ambient_temp_C=ambient_temp)

# Output
st.metric("Air Density (kg/m³)", f"{rho:.2f}")
st.metric("Lift Force (N)", f"{lift_force:.1f}")
st.metric("Drag Force (N)", f"{drag_force:.1f}")
st.metric("Propulsion Power (W)", f"{propulsion_power:.1f}")
st.metric("Battery Draw (W)", f"{battery_draw:.1f}")
st.metric("Usable Battery (Wh)", f"{usable_battery_wh:.1f}")
st.metric("Flight Time", f"{flight_time_minutes:.1f} min")
st.metric("Thermal Signature ΔT", f"{delta_T:.1f}°C")

if delta_T > 15:
    st.warning("⚠️ High IR visibility risk.")
elif delta_T > 10:
    st.info("🟡 Moderate IR visibility.")
else:
    st.success("🟢 Low IR signature.")
