def compute_phase_energy(modifier, time_min, draw_watt_base, total_weight_kg, base_weight_kg, wind_factor, hybrid_modifier):
    return (draw_watt_base * (total_weight_kg / base_weight_kg) * modifier * wind_factor * hybrid_modifier) * (time_min / 60)







import streamlit as st
import time
import pandas as pd
import matplotlib.pyplot as plt


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
default_battery_wh = float(profile["battery_wh"])
battery_wh = st.number_input("Battery Capacity (Wh)", min_value=10.0, max_value=2000.0, value=default_battery_wh, key='battery_capacity_wh_1')
power_system = profile["power_system"]
ai_capabilities = profile["ai_features"]

st.markdown("**AI Capabilities:** " + (", ".join([f"`{cap}`" for cap in ai_capabilities]) if ai_capabilities else "`None`"))

st.markdown("<span style='color:#4169E1;'>Base weight: {} kg</span>".format(base_weight_kg), unsafe_allow_html=True)
st.markdown("<span style='color:#4169E1;'>Power System: {}</span>".format(power_system), unsafe_allow_html=True)
st.markdown("<span style='color:#4169E1;'>Base draw: {} W</span>".format(draw_watt_base), unsafe_allow_html=True)

payload_slider = st.slider("Payload Weight (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5), key='payload_weight_g_1')
payload = st.number_input("Payload (g)", min_value=0, max_value=profile["max_payload_g"], value=payload_slider, key='payload_g_1')
speed_slider = st.slider("Flight Speed (km/h)", 10, 150, 40, key='flight_speed_km/h_4')
speed = st.number_input("Flight Speed (km/h)", min_value=10, max_value=150, value=speed_slider, key='flight_speed_km/h_5')
altitude_slider = st.slider("Target Altitude (m)", 0, 3000, 200, key='target_altitude_m_2')
altitude = st.number_input("Target Altitude (m)", min_value=0, max_value=3000, value=altitude_slider, key='target_altitude_m_3')
temperature_slider = st.slider("Temperature (Â°C)", -10, 45, 25, key='temperature_Â°c_2')
temperature = st.number_input("Temperature (Â°C)", min_value=-10, max_value=45, value=temperature_slider, key='temperature_Â°c_3')
speed_slider = st.slider("Flight Speed (km/h)", 10, 150, 40, key='flight_speed_km/h_6')
speed = st.number_input("Flight Speed (km/h)", min_value=10, max_value=150, value=speed_slider, key='flight_speed_km/h_7')

st.markdown("<h5 style='color:#4169E1;'>Mission Profile (Time-Based)</h5>", unsafe_allow_html=True)
climb_slider = st.slider("Climb Time (min)", 0, 30, 2, key='climb_time_min_2')
climb_time = st.number_input("Climb Time (min)", min_value=0, max_value=30, value=climb_slider, key='climb_time_min_3')
cruise_slider = st.slider("Cruise Time (min)", 0, 60, 8, key='cruise_time_min_2')
cruise_time = st.number_input("Cruise Time (min)", min_value=0, max_value=60, value=cruise_slider, key='cruise_time_min_3')
descent_slider = st.slider("Descent Time (min)", 0, 30, 2, key='descent_time_min_2')
descent_time = st.number_input("Descent Time (min)", min_value=0, max_value=30, value=descent_slider, key='descent_time_min_3')
total_mission_time = climb_time + cruise_time + descent_time

submitted = st.button("âï¸ Estimate")

if submitted:
    if profile["max_payload_g"] > 0 and payload > profile["max_payload_g"] * 0.85:
        st.warning("Payload exceeds 85% of max capacity â flight efficiency drops sharply.")
    total_weight_kg = base_weight_kg + payload / 1000

    # Wind logic
    wind_slider = st.slider("Wind Speed (km/h)", 0, 100, 10, key="wind_slider")
    wind_speed = st.number_input("Wind Speed (km/h)", min_value=0, max_value=100, value=wind_slider, key="wind_input")
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
    if flight_time_min < 5:
        st.error("Estimated flight time is very low. Consider adjusting payload or profile.")
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

    
    # Battery Simulator
    st.markdown("<h4 style='color:#4169E1;'>Battery Simulator</h4>", unsafe_allow_html=True)
    time_step = 10
    total_steps = max(1, int(flight_time_min * 60 / time_step))
    battery_per_step = (total_energy_wh / flight_time_min) * (time_step / 60)
    progress = st.progress(0)
    gauge = st.empty()
    timer = st.empty()

    battery_data = []

    for step in range(total_steps + 1):
        time_elapsed = step * time_step
        battery_used = step * battery_per_step
        battery_remaining = max(0, battery_wh - battery_used)
        battery_pct = max(0, (battery_remaining / battery_wh) * 100)
        time_remaining = max(0, (flight_time_min * 60) - time_elapsed)
        bars = int(battery_pct // 10)

        gauge.markdown(f"<span style='color:#4169E1;'>Battery Gauge: [{'|' * bars}{' ' * (10 - bars)}] {battery_pct:.0f}%</span>", unsafe_allow_html=True)
        timer.markdown(f"<span style='color:#4169E1;'>Elapsed: {time_elapsed} secâRemaining: {int(time_remaining)} sec</span>", unsafe_allow_html=True)
        progress.progress(min(step / total_steps, 1.0))
        battery_data.append((time_elapsed, battery_pct))
        time.sleep(0.05)

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
