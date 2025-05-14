
import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")
st.caption("Realistic scaling, wind drag, crash logic, and digital UI enhancements.")

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "draw_watt_base": 170, "battery_wh": 60, "power_system": "Battery"},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "draw_watt_base": 180, "battery_wh": 68, "power_system": "Battery"},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "draw_watt_base": 100, "battery_wh": 50, "power_system": "Battery"},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "draw_watt_base": 250, "battery_wh": 275, "power_system": "Battery"},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "draw_watt_base": 900, "battery_wh": 150, "power_system": "Hybrid"},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "draw_watt_base": 1100, "battery_wh": 200, "power_system": "Hybrid"},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "draw_watt_base": 130, "battery_wh": 45, "power_system": "Battery"},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "draw_watt_base": 450, "battery_wh": 710, "power_system": "Battery"},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "draw_watt_base": 300, "battery_wh": 100, "power_system": "Hybrid"},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "draw_watt_base": 240, "battery_wh": 150, "power_system": "Battery"}
}

model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[model]
base_weight_kg = profile["base_weight_kg"]
draw_watt_base = profile["draw_watt_base"]
default_battery_wh = profile["battery_wh"]
power_system = profile["power_system"]

st.caption(f"Base weight: {base_weight_kg} kg")
st.markdown(f"<span style='color:#00FF00;font-weight:bold;'>Power System: {power_system}</span>", unsafe_allow_html=True)
st.caption(f"Base draw: {draw_watt_base} W")

battery_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, max_value=2000.0, value=float(default_battery_wh), step=1.0)

with st.container():
    st.markdown("<h5 style='color:#3399FF;'>Payload, Speed & Altitude</h5>", unsafe_allow_html=True)
    payload = st.slider("Payload Weight (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5))
    speed = st.slider("Flight Speed (km/h)", 10, 150, 40)
    wind = st.slider("Wind Speed (km/h)", 0, 50, 10)
    altitude = st.slider("Flight Altitude (m)", 0, 3000, 200)
    temperature_c = st.slider("Temperature (°C)", -20, 60, 25)

flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward", "Cruise"])

# Apply temperature effect
if temperature_c < 15:
    battery_wh *= 0.9
elif temperature_c > 35:
    battery_wh *= 0.95

total_weight_kg = base_weight_kg + payload / 1000

# Crash risk simulation for hybrid drones
if power_system == "Hybrid":
    if temperature_c > 40 and altitude > 2000 and payload > profile["max_payload_g"] * 0.9:
        st.error("SIMULATION FAILURE: Hybrid backup system failure due to high stress conditions.")
        st.stop()

# Power draw scaling
air_density = max(0.6, 1.0 - 0.01 * (altitude / 100))
efficiency_factor = 1 + (payload / (profile["max_payload_g"] + 1e-6)) * 0.3
speed_factor = 1 + 0.01 * (speed - 30) if speed > 30 else 1
wind_penalty = 1 + 0.004 * wind

draw_scaled = draw_watt_base * (total_weight_kg / base_weight_kg) * efficiency_factor * speed_factor * wind_penalty / air_density

st.subheader("Estimated Results")
flight_time_min = (battery_wh / draw_scaled) * 60
distance_km = (flight_time_min / 60) * speed

st.metric("Flight Time", f"{flight_time_min:.1f} min")
st.metric("Max Distance", f"{distance_km:.2f} km")
st.metric("Power Draw", f"{draw_scaled:.0f} W")

# Battery simulator
st.subheader("Battery Simulator")
time_step = 10
total_steps = max(1, int(flight_time_min * 60 / time_step))
battery_per_step = (draw_scaled * time_step) / 3600
progress = st.progress(0)
gauge = st.empty()
timer = st.empty()

for step in range(total_steps + 1):
    time_elapsed = step * time_step
    battery_remaining = battery_wh - (step * battery_per_step)
    battery_pct = max(0, (battery_remaining / battery_wh) * 100)
    time_remaining = max(0, (flight_time_min * 60) - time_elapsed)
    bars = int(battery_pct // 10)
    gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {battery_pct:.0f}%`")
    timer.markdown(f"**Elapsed:** {time_elapsed} sec **Remaining:** {int(time_remaining)} sec")
    progress.progress(min(step / total_steps, 1.0))
    time.sleep(0.05)

st.success("Simulation complete.")
st.caption("GPT-UAV Planner | 2025 — Enhanced UI with blue sliders and live gauge.")

