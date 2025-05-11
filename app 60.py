
import streamlit as st
import time
import os

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.markdown("<h1 style=\"text-align: center; color: #33cccc; font-size: 2.5em;\">UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 170, "battery_wh": 60, "crash_risk": False},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 180, "battery_wh": 68, "crash_risk": False},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 100, "battery_wh": 50, "crash_risk": False},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 250, "battery_wh": 275, "crash_risk": False},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 900, "battery_wh": 150, "crash_risk": True},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 1100, "battery_wh": 200, "crash_risk": True},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 130, "battery_wh": 45, "crash_risk": False},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 450, "battery_wh": 710, "crash_risk": False},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 300, "battery_wh": 100, "crash_risk": True},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 240, "battery_wh": 150, "crash_risk": False}
}

debug_mode = st.checkbox("Enable Debug Mode")

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()) + ["Custom Build"])

image_file_map = {
    "Generic Quad": "generic_quad.png",
    "DJI Phantom": "dji_phantom.png",
    "RQ-11 Raven": "rq11_raven.png",
    "RQ-20 Puma": "rq20_puma.png",
    "Skydio 2+": "skydio2plus.png",
    "MQ-1 Predator": "mq1_predator.png",
    "MQ-9 Reaper": "mq9_reaper.png",
    "Teal Golden Eagle": "teal_golden_eagle.png",
    "Freefly Alta 8": "freefly_alta8_black.png",
    "Quantum Systems Vector": "quantum_vector.png"
}

if drone_model in image_file_map:
    image_path = os.path.join("images", image_file_map[drone_model])
    if os.path.exists(image_path):
        st.image(image_path, caption=f"{drone_model} (Cartoon View)", use_container_width=True)

# — Flight Parameters & Simulation — simplified here for brevity

st.caption("Air density and AI tips included. Full simulation code should integrate into the form submit block.")

