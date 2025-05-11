
import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 170, "battery_wh": 60},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 180, "battery_wh": 81.3},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 100, "battery_wh": 24.3},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 250, "battery_wh": 275},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 900, "battery_wh": 150},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 1100, "battery_wh": 200},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 130, "battery_wh": 65.1},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 450, "battery_wh": 532.8},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 300, "battery_wh": 100},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 240, "battery_wh": 180}
}

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()) + ["Custom Build"])

if drone_model == "Custom Build":
    st.markdown("**Custom Lift Calculation:**")
    num_motors = st.number_input("Number of Motors", min_value=1, value=4)
    thrust_per_motor = st.number_input("Thrust per Motor (g)", min_value=100, value=1000)
    base_weight_kg = 1.2
    max_lift = (num_motors * thrust_per_motor) - 600 - 400
    if max_lift <= 0:
        st.error("Invalid configuration: calculated max payload is non-positive.")
        st.stop()
    st.caption(f"Calculated max payload capacity: {int(max_lift)} g")
    default_battery = 50.0
else:
    profile = UAV_PROFILES[drone_model]
    max_lift = profile["max_payload_g"]
    base_weight_kg = profile["base_weight_kg"]
    st.caption(f"Base weight: {base_weight_kg:.2f} kg — Max payload: {max_lift} g")
    st.caption(f"Power system: `{profile['power_system']}`")
    default_battery = profile["battery_wh"]

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, max_value=1850.0, value=float(default_battery))
    default_payload = int(max_lift * 0.5)
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, value=default_payload)
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")
    submitted = st.form_submit_button("Estimate")

if submitted:
    try:
        if payload_weight_g > max_lift:
            st.error("Payload exceeds lift capacity. The drone cannot take off with this configuration.")
            st.stop()

        total_weight_kg = base_weight_kg + (payload_weight_g / 1000)
        if temperature_c < 15:
            battery_capacity_wh *= 0.9
        elif temperature_c > 35:
            battery_capacity_wh *= 0.95

        air_density_factor = max(0.6, 1.0 - 0.01 * (altitude_m / 100))
        hover_power = 170 * (total_weight_kg ** 1.5) / air_density_factor

        if flight_mode == 'Hover':
            total_power_draw = hover_power
        elif flight_mode == 'Forward Flight':
            total_power_draw = hover_power * 1.15 + 0.02 * (flight_speed_kmh ** 2) + 0.3 * wind_speed_kmh
        elif flight_mode == 'Waypoint Mission':
            total_power_draw = hover_power * 1.25 + 0.022 * (flight_speed_kmh ** 2) + 0.36 * wind_speed_kmh

        load_ratio = payload_weight_g / max_lift if max_lift > 0 else 0
        efficiency_penalty = 1
        if 0.7 <= load_ratio < 0.9:
            efficiency_penalty = 1.1
        elif 0.9 <= load_ratio <= 1.0:
            efficiency_penalty = 1.25
        elif load_ratio > 1.0:
            efficiency_penalty = 1.4

        if drone_model != "Custom Build" and UAV_PROFILES[drone_model]["power_system"] == "Hybrid":
            base_draw = UAV_PROFILES[drone_model]["draw_watt"]
            drag_factor = 1.0
            if flight_mode == 'Forward Flight':
                drag_factor += 0.01 * flight_speed_kmh + 0.001 * (altitude_m / 100)
            elif flight_mode == 'Waypoint Mission':
                drag_factor += 0.012 * flight_speed_kmh + 0.0012 * (altitude_m / 100)
            mass_penalty = 1.0 + 0.003 * total_weight_kg
            drag_factor *= mass_penalty
            drag_factor = min(drag_factor, 2.2)
            total_draw = base_draw * drag_factor
        else:
            total_draw = total_power_draw * efficiency_penalty

        if elevation_gain_m > 0:
            climb_energy_j = total_weight_kg * 9.81 * elevation_gain_m
            climb_energy_wh = climb_energy_j / 3600
            battery_capacity_wh -= climb_energy_wh
        elif elevation_gain_m < 0:
            descent_energy_j = total_weight_kg * 9.81 * abs(elevation_gain_m)
            battery_capacity_wh += (descent_energy_j / 3600) * 0.2

        if battery_capacity_wh <= 0:
            st.info("Simulation stopped: energy usage exceeded battery capacity.")
            st.stop()

        flight_time_minutes = (battery_capacity_wh / total_draw) * 60
        flight_time_minutes = min(flight_time_minutes, 120)

        st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)

st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")
