
import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 170, "battery_wh": 60, "crash_risk": False, "max_speed_kmh": 60, "max_altitude_m": 500},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 180, "battery_wh": 68, "crash_risk": False, "max_speed_kmh": 70, "max_altitude_m": 600},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 100, "battery_wh": 50, "crash_risk": False, "max_speed_kmh": 60, "max_altitude_m": 300},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 250, "battery_wh": 275, "crash_risk": False, "max_speed_kmh": 65, "max_altitude_m": 500},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 900, "battery_wh": 1200, "crash_risk": True, "max_speed_kmh": 217, "max_altitude_m": 7500},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 1100, "battery_wh": 2000, "crash_risk": True, "max_speed_kmh": 300, "max_altitude_m": 13000},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 130, "battery_wh": 45, "crash_risk": False, "max_speed_kmh": 58, "max_altitude_m": 400},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 450, "battery_wh": 710, "crash_risk": False, "max_speed_kmh": 80, "max_altitude_m": 1200},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 300, "battery_wh": 100, "crash_risk": True, "max_speed_kmh": 80, "max_altitude_m": 1000},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 240, "battery_wh": 150, "crash_risk": False, "max_speed_kmh": 75, "max_altitude_m": 2000}
}

# Ensure this section always renders first
debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()) + ["Custom Build"])

# Placeholder info
st.markdown("*Air density and AI tips included. Full simulation code should integrate into the form submit block.*")

