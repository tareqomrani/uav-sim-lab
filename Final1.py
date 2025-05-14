
import streamlit as st
import time
import pandas as pd
import matplotlib.pyplot as plt

def compute_phase_energy(modifier, time_min, draw_watt_base, total_weight_kg, base_weight_kg, wind_factor, hybrid_modifier):
    return (draw_watt_base * (total_weight_kg / base_weight_kg) * modifier * wind_factor * hybrid_modifier) * (time_min / 60)

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")

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
battery_wh = float(profile["battery_wh"])
power_system = profile["power_system"]
ai_capabilities = profile["ai_features"]

st.markdown("**AI Capabilities:** " + (", ".join([f"`{cap}`" for cap in ai_capabilities]) if ai_capabilities else "`None`"))

st.markdown("<span style='color:#4169E1;'>Base weight: {} kg</span>".format(base_weight_kg), unsafe_allow_html=True)
st.markdown("<span style='color:#4169E1;'>Power System: {}</span>".format(power_system), unsafe_allow_html=True)
st.markdown("<span style='color:#4169E1;'>Base draw: {} W</span>".format(draw_watt_base), unsafe_allow_html=True)

payload = st.slider("Payload Weight (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5)) if profile["max_payload_g"] > 0 else 0
speed = st.slider("Flight Speed (km/h)", 10, 150, 40)
altitude = st.slider("Target Altitude (m)", 0, 3000, 200)
temperature = st.slider("Temperature (°C)", -10, 45, 25)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)

st.markdown("<h5 style='color:#4169E1;'>Mission Profile (Time-Based)</h5>", unsafe_allow_html=True)
climb_time = st.slider("Climb Time (min)", 0, 30, 2)
cruise_time = st.slider("Cruise Time (min)", 0, 60, 8)
descent_time = st.slider("Descent Time (min)", 0, 30, 2)
total_mission_time = climb_time + cruise_time + descent_time

submitted = st.button("✈️ Estimate")

if submitted:
    total_weight_kg = base_weight_kg + payload / 1000

    # Wind logic
    wind_factor = 1 + (wind_speed / 100) * 0.1

    # Hybrid logic
    if power_system == "Hybrid":
        if speed < 40:
            hybrid_modifier = 1.0
        elif speed <= 100:
            hybrid_modifier = 0.85 - 0.001 * (speed - 40)
        else:
            hybrid_modifier = 0.80
    else:
        hybrid_modifier = 1.0

    # Temperature correction
    adjusted_battery_wh = battery_wh
    if temperature < 15:
        adjusted_battery_wh *= 0.9
    elif temperature > 35:
        adjusted_battery_wh *= 0.95

    # Phase energy usage
    climb_modifier = 1.15
    cruise_modifier = 1.0
    descent_modifier = 0.85

    cruise_energy = compute_phase_energy(cruise_modifier, cruise_time, draw_watt_base, total_weight_kg, base_weight_kg, wind_factor, hybrid_modifier)
    descent_energy = compute_phase_energy(descent_modifier, descent_time, draw_watt_base, total_weight_kg, base_weight_kg, wind_factor, hybrid_modifier)

    # Climb energy from altitude (mgh)
    g = 9.81
    climb_energy = total_weight_kg * g * altitude / 3600

    total_energy_wh = climb_energy + cruise_energy + descent_energy
    net_energy_available = adjusted_battery_wh
    flight_time_min = total_mission_time
    distance_km = (speed * total_mission_time) / 60

    # Return-to-home reserve
    battery_reserve_wh = battery_wh * 0.10
    if total_energy_wh + battery_reserve_wh > net_energy_available:
        st.error("Insufficient battery for mission including 10% return-to-home reserve!")
    else:
        st.info(f"10% battery reserved for return-to-home: {battery_reserve_wh:.1f} Wh")

    st.markdown("<h4 style='color:#4169E1;'>Estimated Results</h4>", unsafe_allow_html=True)
    st.metric("Flight Time", f"{flight_time_min:.1f} min")
    st.metric("Max Distance", f"{distance_km:.2f} km")
    st.metric("Total Energy Used", f"{total_energy_wh:.1f} Wh")

    # Chart
    st.markdown("<h4 style='color:#4169E1;'>Phase Energy Usage</h4>", unsafe_allow_html=True)
    phase_labels = ['Climb', 'Cruise', 'Descent']
    energy_values = [climb_energy, cruise_energy, descent_energy]
    fig2, ax2 = plt.subplots()
    ax2.bar(phase_labels, energy_values)
    ax2.set_ylabel("Energy (Wh)")
    ax2.set_title("Energy Used Per Flight Phase")
    st.pyplot(fig2)

st.markdown("<span style='color:#4169E1;'>GPT-UAV Planner | Final Stable Version</span>", unsafe_allow_html=True)

