import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.markdown("<h1 style='text-align: center; color: #33cccc; font-size: 2.5em;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)

UAV_PROFILES = {
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 1100, "battery_wh": 2000, "crash_risk": True, "max_speed_kmh": 300, "max_altitude_m": 13000},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 900, "battery_wh": 1200, "crash_risk": True, "max_speed_kmh": 217, "max_altitude_m": 7500},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 250, "battery_wh": 275, "crash_risk": False, "max_speed_kmh": 65, "max_altitude_m": 500},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 100, "battery_wh": 75, "crash_risk": False, "max_speed_kmh": 60, "max_altitude_m": 300},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 300, "battery_wh": 110, "crash_risk": True, "max_speed_kmh": 80, "max_altitude_m": 1000},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 240, "battery_wh": 150, "crash_risk": False, "max_speed_kmh": 75, "max_altitude_m": 2000}
}

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))

profile = UAV_PROFILES[drone_model]
max_lift = profile["max_payload_g"]
base_weight_kg = profile["base_weight_kg"]
st.caption(f"Base weight: {base_weight_kg:.2f} kg — Max payload: {max_lift} g")
st.caption(f"Power system: `{profile['power_system']}`")

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=float(profile["battery_wh"]))
    default_payload = int(max_lift * 0.5)
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, max_value=int(max_lift), value=default_payload)
    if payload_weight_g > max_lift:
        st.error("SIMULATION STOPPED: Payload exceeds maximum lift capacity.")
        st.stop()
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    if flight_speed_kmh > profile["max_speed_kmh"]:
        st.warning(f"{drone_model} speed capped at {profile['max_speed_kmh']} km/h.")
        flight_speed_kmh = profile["max_speed_kmh"]
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=15000, value=0)
    if altitude_m > profile["max_altitude_m"]:
        st.warning(f"{drone_model} altitude capped at {profile['max_altitude_m']} m.")
        altitude_m = profile["max_altitude_m"]
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")
    submitted = st.form_submit_button("Estimate")

if submitted:
    try:
        total_weight_kg = base_weight_kg + (payload_weight_g / 1000)
        if temperature_c < 15:
            temp_penalty = 0.9
        elif temperature_c > 35:
            temp_penalty = 0.95
        else:
            temp_penalty = 1.0
        battery_capacity_wh *= temp_penalty
        base_hover_efficiency = 170
        air_density_factor = max(0.6, 1.0 - 0.01 * (altitude_m / 100))
        hover_power = base_hover_efficiency * (total_weight_kg ** 1.5) / air_density_factor
        if flight_mode == 'Hover':
            total_power_draw = hover_power
        elif flight_mode == 'Forward Flight':
            total_power_draw = hover_power * 1.15 + 0.02 * (flight_speed_kmh ** 2) + 0.3 * wind_speed_kmh
        elif flight_mode == 'Waypoint Mission':
            total_power_draw = hover_power * 1.25 + 0.022 * (flight_speed_kmh ** 2) + 0.36 * wind_speed_kmh
        load_ratio = payload_weight_g / max_lift if max_lift > 0 else 0
        efficiency_penalty = 1.0
        if 0.7 <= load_ratio < 0.9:
            efficiency_penalty = 1.1
        elif 0.9 <= load_ratio <= 1.0:
            efficiency_penalty = 1.25
        elif load_ratio > 1.0:
            efficiency_penalty = 1.4
        if profile["power_system"] == "Hybrid":
            base_draw = profile["draw_watt"]
            drag_factor = 1.0
            if flight_mode == 'Forward Flight':
                drag_factor += 0.01 * flight_speed_kmh + 0.001 * (altitude_m / 100)
            elif flight_mode == 'Waypoint Mission':
                drag_factor += 0.012 * flight_speed_kmh + 0.0012 * (altitude_m / 100)
            drag_factor *= 1.0 + 0.003 * total_weight_kg
            drag_factor = min(drag_factor, 2.2)
            total_draw = base_draw * drag_factor
        else:
            total_draw = total_power_draw * efficiency_penalty
        if elevation_gain_m > 0:
            climb_energy_j = total_weight_kg * 9.81 * elevation_gain_m
            battery_capacity_wh -= climb_energy_j / 3600
        elif elevation_gain_m < 0:
            descent_energy_j = total_weight_kg * 9.81 * abs(elevation_gain_m)
            battery_capacity_wh += (descent_energy_j / 3600) * 0.2
        if simulate_failure and profile["power_system"] == "Hybrid" and profile["crash_risk"]:
            if temperature_c > 35 or elevation_gain_m > 300 or (total_weight_kg > 100 and wind_speed_kmh > 20):
                st.error("SIMULATION FAILURE: Battery backup failure conditions met.")
                st.stop()
        if battery_capacity_wh <= 0:
            st.info("Simulation stopped: energy usage exceeded battery capacity.")
            st.stop()
        flight_time_minutes = (battery_capacity_wh / total_draw) * 60
        flight_time_minutes = min(flight_time_minutes, 1850)
        st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")
        st.subheader("AI Suggestions (Simulated GPT)")
        if flight_speed_kmh > 40:
            st.markdown("**Tip:** High flight speed increases drag and draw.")
        if payload_weight_g > max_lift * 0.9:
            st.markdown("**Tip:** Near max payload reduces stability.")
        if wind_speed_kmh > 20:
            st.markdown("**Tip:** Strong wind increases draw.")
        if temperature_c < 0 or temperature_c > 40:
            st.markdown("**Tip:** Extreme temperatures reduce battery efficiency.")
        if elevation_gain_m > 300:
            st.markdown("**Tip:** Climbing over 300m significantly reduces range.")
        st.subheader("Live Simulation")
        time_step = 10
        total_steps = max(1, int(flight_time_minutes * 60 / time_step))
        battery_per_step = (total_draw * time_step) / 3600
        progress = st.progress(0)
        status = st.empty()
        gauge = st.empty()
        timer = st.empty()
        for step in range(total_steps + 1):
            time_elapsed = step * time_step
            battery_remaining = battery_capacity_wh - (step * battery_per_step)
            battery_pct = max(0, (battery_remaining / battery_capacity_wh) * 100)
            time_remaining = max(0, (flight_time_minutes * 60) - time_elapsed)
            bars = int(battery_pct // 10)
            gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {battery_pct:.0f}%`")
            timer.markdown(f"**Elapsed:** {time_elapsed} sec **Remaining:** {int(time_remaining)} sec")
status.markdown(f"**Battery Remaining:** {battery_remaining:.2f} Wh  \n**Power Draw:** {total_draw:.0f} W")
**Power Draw:** {total_draw:.0f} W")
            progress.progress(min(step / total_steps, 1.0))
            time.sleep(0.01)
        st.success("Simulation complete.")
    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)

st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")