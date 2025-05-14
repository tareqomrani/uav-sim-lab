
import streamlit as st
import time
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")

# UI Title (with wind and color updates)
st.markdown("<h1 style='color:#00FF00;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
st.markdown("<span style='color:#00FF00;'>Includes climb/descent logic, air density adjustments, and onboard AI capabilities.</span>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)

UAV_PROFILES = {
    "Generic Quad": {
        "max_payload_g": 800, "base_weight_kg": 1.2, "draw_watt_base": 170, "battery_wh": 60,
        "power_system": "Battery", "ai_features": ["Obstacle Avoidance"]
    },
    "DJI Phantom": {
        "max_payload_g": 500, "base_weight_kg": 1.4, "draw_watt_base": 180, "battery_wh": 68,
        "power_system": "Battery", "ai_features": ["Obstacle Avoidance", "Auto-Landing"]
    },
    "RQ-11 Raven": {
        "max_payload_g": 0, "base_weight_kg": 1.9, "draw_watt_base": 100, "battery_wh": 50,
        "power_system": "Battery", "ai_features": []
    },
    "RQ-20 Puma": {
        "max_payload_g": 600, "base_weight_kg": 6.3, "draw_watt_base": 250, "battery_wh": 275,
        "power_system": "Battery", "ai_features": ["Auto Navigation"]
    },
    "MQ-1 Predator": {
        "max_payload_g": 204000, "base_weight_kg": 512, "draw_watt_base": 900, "battery_wh": 150,
        "power_system": "Hybrid", "ai_features": ["Auto Targeting", "Route Optimization"]
    },
    "MQ-9 Reaper": {
        "max_payload_g": 1700000, "base_weight_kg": 2223, "draw_watt_base": 1100, "battery_wh": 200,
        "power_system": "Hybrid", "ai_features": ["Auto Targeting", "Route Optimization", "Obstacle Avoidance"]
    },
    "Skydio 2+": {
        "max_payload_g": 150, "base_weight_kg": 0.8, "draw_watt_base": 130, "battery_wh": 45,
        "power_system": "Battery", "ai_features": ["360 Vision", "Autonomous Flight"]
    },
    "Freefly Alta 8": {
        "max_payload_g": 9000, "base_weight_kg": 6.2, "draw_watt_base": 450, "battery_wh": 710,
        "power_system": "Battery", "ai_features": ["Redundant AI", "Auto-Landing"]
    },
    "Teal Golden Eagle": {
        "max_payload_g": 2000, "base_weight_kg": 2.2, "draw_watt_base": 300, "battery_wh": 100,
        "power_system": "Hybrid", "ai_features": ["Obstacle Avoidance", "Route Optimization"]
    },
    "Quantum Systems Vector": {
        "max_payload_g": 1500, "base_weight_kg": 2.3, "draw_watt_base": 240, "battery_wh": 150,
        "power_system": "Battery", "ai_features": ["Autonomous Pathing"]
    }
}

model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[model]
base_weight_kg = profile["base_weight_kg"]
draw_watt_base = profile["draw_watt_base"]
battery_wh_input = float(profile["battery_wh"])
battery_wh = st.number_input("Battery Capacity (Wh)", min_value=10.0, max_value=1850.0, value=battery_wh_input)
power_system = profile["power_system"]
ai_capabilities = profile["ai_features"]

# AI Feature Display
if ai_capabilities:
    st.markdown("**AI Capabilities:** " + ", ".join([f"`{cap}`" for cap in ai_capabilities]))
else:
    st.markdown("**AI Capabilities:** `None`")

st.markdown(f"<span style='color:#00FF00;'>Base weight: {base_weight_kg} kg</span>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
st.markdown(f"<span style='color:#00FF00;'>Power System: {power_system}</span>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
st.markdown(f"<span style='color:#00FF00;'>Base draw: {draw_watt_base} W</span>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)

# UI Sliders
st.markdown("<h5 style='color:#00FF00;'>Flight Parameters</h5>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
if profile["max_payload_g"] > 0:
    payload = st.slider("Payload Weight (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5))
else:
    payload = 0
    st.warning("Note: This drone has no payload capacity.")

speed = st.slider("Flight Speed (km/h)", 10, 150, 40)
altitude = st.slider("Target Altitude (m)", 0, 3000, 200)
temperature = st.slider("Temperature (°C)", -10, 45, 25)

# Multi-phase flight profile
st.markdown("<h5 style='color:#4169E1;'>Mission Profile (Time-Based)</h5>", unsafe_allow_html=True)
climb_time = st.slider("Climb Time (min)", 0, 30, 2)
cruise_time = st.slider("Cruise Time (min)", 0, 60, 8)
descent_time = st.slider("Descent Time (min)", 0, 30, 2)
total_mission_time = climb_time + cruise_time + descent_time


# Estimate button
submitted = st.button("✈️ Estimate")
if submitted:
    total_weight_kg = base_weight_kg + payload / 1000

    # Refined air density based on simplified ISA model
    air_density = max(0.5, 1.225 * (1 - 0.0000225577 * altitude) ** 5.25588)

    efficiency_factor = 1 + (payload / max(1, profile["max_payload_g"])) * 0.3
    speed_factor = 1 + 0.01 * (speed - 30) if speed > 30 else 1

    # Temperature adjustment
    adjusted_battery_wh = battery_wh
    if temperature < 15:
        adjusted_battery_wh *= 0.9
        st.warning("Cold temperatures reduce battery efficiency.")
    elif temperature > 35:
        adjusted_battery_wh *= 0.95
        st.warning("High temperatures degrade battery performance.")

    # Climb energy cost (mgh in joules -> wh)
    g = 9.81
    climb_energy_j = total_weight_kg * g * altitude
    climb_energy_wh = climb_energy_j / 3600

    # Descent recovery (10% of climb energy if descending)
    descent_recovery = 0
    if altitude > 100:
        descent_recovery = climb_energy_wh * 0.1

    net_energy_available = adjusted_battery_wh - climb_energy_wh + descent_recovery

    
    # Wind impact: assume linear +/-10% effect
    if wind_speed >= 0:
        wind_factor = 1 + (wind_speed / 100) * 0.1  # headwind increases draw
    else:
        wind_factor = 1 - (abs(wind_speed) / 100) * 0.1  # tailwind reduces draw

# Phase-based power modifier
    phase_modifier = 1.0
    if phase == "Climb":
        phase_modifier = 1.15
    elif phase == "Cruise":
        phase_modifier = 1.0
    elif phase == "Descent":
        phase_modifier = 0.85
draw_scaled = draw_watt_base * (total_weight_kg / base_weight_kg) * phase_modifier * wind_factor * efficiency_factor * speed_factor / air_density

    # Phase modifiers
    def compute_phase_energy(modifier, time_min):
        return (draw_watt_base * (total_weight_kg / base_weight_kg) * modifier * wind_factor * hybrid_modifier) * (time_min / 60)

    climb_modifier = 1.15
    cruise_modifier = 1.0
    descent_modifier = 0.85

    climb_energy = compute_phase_energy(climb_modifier, climb_time)
    cruise_energy = compute_phase_energy(cruise_modifier, cruise_time)
    descent_energy = compute_phase_energy(descent_modifier, descent_time)

    total_energy_wh = climb_energy + cruise_energy + descent_energy
    flight_time_min = total_mission_time
    distance_km = (speed * total_mission_time) / 60
    net_energy_available = adjusted_battery_wh
    if total_energy_wh > net_energy_available:
        st.error('Insufficient battery for this mission profile!')
    distance_km = (flight_time_min / 60) * speed

    st.markdown("<h4 style='color:#4169E1;'>Estimated Results</h4>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
    st.metric("Flight Time", f"{flight_time_min:.1f} min")
    st.metric("Max Distance", f"{distance_km:.2f} km")
    st.metric("Power Draw", f"{draw_scaled:.0f} W")

    # AI Warnings
    if payload > profile["max_payload_g"] * 0.85:
        st.warning("Payload exceeds 85% of max capacity — flight efficiency drops sharply.")
    if flight_time_min < 5:
        st.error("Critical: Estimated flight time is very low. Consider reducing payload or altitude.")

    # Battery Simulator
    st.markdown("<h4 style='color:#4169E1;'>Battery Simulator</h4>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
    time_step = 10
    total_steps = max(1, int(flight_time_min * 60 / time_step))
    battery_per_step = (draw_scaled * time_step) / 3600
    progress = st.progress(0)
    gauge = st.empty()
    timer = st.empty()

    battery_data = []

    for step in range(total_steps + 1):
        time_elapsed = step * time_step
        battery_remaining = net_energy_available - (step * battery_per_step)
        battery_pct = max(0, (battery_remaining / battery_wh) * 100)
        time_remaining = max(0, (flight_time_min * 60) - time_elapsed)
        bars = int(battery_pct // 10)

        gauge.markdown(f"<span style='color:#00FF00;'>Battery Gauge: [{'|' * bars}{' ' * (10 - bars)}] {battery_pct:.0f}%</span>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
        timer.markdown(f"<span style='color:#00FF00;'>Elapsed: {time_elapsed} sec Remaining: {int(time_remaining)} sec</span>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
        progress.progress(min(step / total_steps, 1.0))
        battery_data.append((time_elapsed, battery_pct))
        time.sleep(0.05)

    df_battery = pd.DataFrame(battery_data, columns=["Time (s)", "Battery %"])
    st.markdown("<h4 style='color:#4169E1;'>Battery Usage Over Time</h4>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)
    fig, ax = plt.subplots()
    ax.plot(df_battery["Time (s)"], df_battery["Battery %"])
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Battery %")
    ax.set_title("Battery Drain Simulation")
    st.pyplot(fig)

st.markdown("<span style='color:#4169E1;'>GPT-UAV Planner | 2025 — Enhanced AI-Aware Simulation Mode<br><br>Built by Tareq Omrani</span>", unsafe_allow_html=True)
wind_speed = st.slider("Wind Speed (km/h)", 0, 100, 10)

    # Phase Energy Breakdown Chart
    st.markdown("<h4 style='color:#4169E1;'>Phase Energy Usage</h4>", unsafe_allow_html=True)
    phase_labels = ['Climb', 'Cruise', 'Descent']
    energy_values = [climb_energy, cruise_energy, descent_energy]

    fig2, ax2 = plt.subplots()
    ax2.bar(phase_labels, energy_values)
    ax2.set_ylabel("Energy (Wh)")
    ax2.set_title("Energy Used Per Flight Phase")
    st.pyplot(fig2)
