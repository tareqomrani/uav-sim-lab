import streamlit as st

# Mission phase durations (minutes)
climb_time = 5
cruise_time = 20
descent_time = 5



# Define required time-phase constants BEFORE any usage

# Default time phase settings (minutes)

# Default time phase settings (minutes)









import time
import pandas as pd
import matplotlib.pyplot as plt

# Default time phase settings (minutes)


st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.markdown("""
<div style="text-align: center; padding: 10px;">
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style='text-align:center; padding:10px;'>
</div>
""", unsafe_allow_html=True)

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "draw_watt_base": 170, "battery_wh": 60, "power_system": "Battery", "ai_features": ["Obstacle Avoidance"]},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "draw_watt_base": 180, "battery_wh": 68, "power_system": "Battery", "ai_features": ["Obstacle Avoidance", "Auto-Landing"]},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "draw_watt_base": 100, "battery_wh": 50, "power_system": "Battery", "ai_features": []},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "draw_watt_base": 250, "battery_wh": 275, "power_system": "Battery", "ai_features": ["Auto Navigation"]},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "draw_watt_base": 900, "battery_wh": 150, "power_system": "Hybrid", "ai_features": ["Auto Targeting", "Route Optimization"]},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "draw_watt_base": 1100, "battery_wh": 200, "power_system": "Hybrid", "ai_features": ["Auto Targeting", "Route Optimization", "Obstacle Avoidance"]},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "draw_watt_base": 130, "battery_wh": 45, "power_system": "Battery", "ai_features": ["360 Vision", "Autonomous Flight"]},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "draw_watt_base": 450, "battery_wh": 710, "power_system": "Battery", "ai_features": ["Redundant AI", "Auto-Landing"]},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "draw_watt_base": 300, "battery_wh": 100, "power_system": "Hybrid", "ai_features": ["Obstacle Avoidance", "Route Optimization"]},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "draw_watt_base": 240, "battery_wh": 150, "power_system": "Battery", "ai_features": ["Autonomous Pathing"]}
}

st.markdown("<h1 style='color:#4169E1;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)

model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[model]
base_weight_kg = profile["base_weight_kg"]
draw_watt_base = profile["draw_watt_base"]
default_battery_wh = float(profile["battery_wh"])
battery_wh = st.number_input("Battery Capacity (Wh)", min_value=10.0, max_value=2000.0, value=default_battery_wh, key='battery_capacity_wh_1')
power_system = profile["power_system"]
ai_capabilities = profile["ai_features"]

st.markdown("**AI Capabilities:** " + (", ".join([f"`{cap}`" for cap in ai_capabilities]) if ai_capabilities else "`None`"))

st.markdown("<span style='color:#4169E1;'>Base weight: {} kg</span>".format(base_weight_kg), unsafe_allow_html=True)
if profile["max_payload_g"] > 0:
    payload_slider = st.slider("Payload Weight (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5), key="payload_slider_0")
    payload = st.number_input("Payload (g)", min_value=0, max_value=profile["max_payload_g"], value=payload_slider)
else:
    st.markdown("<span style='color:#FFA500;'>Note: This model does not support payloads.</span>", unsafe_allow_html=True)
    payload = 0
st.markdown("<span style='color:#4169E1;'>Power System: {}</span>".format(power_system), unsafe_allow_html=True)
st.markdown("<span style='color:#4169E1;'>Base draw: {} W</span>".format(draw_watt_base), unsafe_allow_html=True)

if profile["max_payload_g"] > 0:
    payload_slider = st.slider("Payload Weight (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5), key="payload_slider_1")
    payload = st.number_input("Payload (g)", min_value=0, max_value=profile["max_payload_g"], value=payload_slider)
else:
    st.markdown("<span style='color:#FFA500;'>Note: This model does not support payloads.</span>", unsafe_allow_html=True)
    payload = 0
speed_slider = st.slider("Flight Speed (km/h)", 10, 150, 40, key="speed_slider_0")
speed = st.number_input("Flight Speed (km/h)", min_value=10, max_value=150, value=speed_slider, key='flight_speed_km/h_5')
altitude_slider = st.slider("Target Altitude (m)", 0, 3000, 200, key='target_altitude_m_2')
altitude = st.number_input("Target Altitude (m)", min_value=0, max_value=3000, value=altitude_slider, key='target_altitude_m_3')
temperature_slider = st.slider("Temperature (°C)", -10, 45, 25, key="temperature_slider_0")
temperature = st.number_input("Temperature (°C)", min_value=-10, max_value=45, value=temperature_slider, key='temperature_°c_3')
speed_slider = st.slider("Flight Speed (km/h)", 10, 150, 40, key="speed_slider_1")
speed = st.number_input("Flight Speed (km/h)", min_value=10, max_value=150, value=speed_slider, key='flight_speed_km/h_7')

st.markdown("<h5 style='color:#4169E1;'>Mission Profile (Time-Based)</h5>", unsafe_allow_html=True)

submitted = st.button("✈️ Estimate")

if submitted:
    if profile["max_payload_g"] > 0 and payload > profile["max_payload_g"] * 0.85:
        st.warning("Payload exceeds 85% of max capacity — flight efficiency drops sharply.")
    total_weight_kg = base_weight_kg + payload / 1000

    # Wind logic
    wind_slider = st.slider("Wind Speed (km/h)", 0, 100, 10, key="wind_slider_0")
    wind_speed = st.number_input("Wind Speed (km/h)", min_value=0, max_value=100, value=wind_slider, key="wind_input")
    wind_factor = 1 + (wind_speed / 100) * 0.1
if speed > 50 and speed <= 100:
    st.write("Cruise speed active.")

st.markdown("<div style='text-align:center; padding-top:20px; color:#4169E1;'>Built by Tareq Omrani — UAV Battery Efficiency Estimator 2025</div>", unsafe_allow_html=True)
