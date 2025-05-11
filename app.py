
import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 170, "battery_wh": 60, "crash_risk": False, "max_speed": 60, "max_altitude": 4000},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 180, "battery_wh": 68, "crash_risk": False, "max_speed": 70, "max_altitude": 5000},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 100, "battery_wh": 50, "crash_risk": False, "max_speed": 65, "max_altitude": 500},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 250, "battery_wh": 275, "crash_risk": False, "max_speed": 80, "max_altitude": 3500},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 900, "battery_wh": 150, "crash_risk": True, "max_speed": 220, "max_altitude": 7500},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 1100, "battery_wh": 200, "crash_risk": True, "max_speed": 300, "max_altitude": 15000},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 130, "battery_wh": 45, "crash_risk": False, "max_speed": 60, "max_altitude": 3000},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 450, "battery_wh": 710, "crash_risk": False, "max_speed": 90, "max_altitude": 4000},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 300, "battery_wh": 100, "crash_risk": True, "max_speed": 100, "max_altitude": 6000},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 240, "battery_wh": 150, "crash_risk": False, "max_speed": 85, "max_altitude": 5000}
}

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))

profile = UAV_PROFILES[drone_model]
max_lift = profile["max_payload_g"]
base_weight_kg = profile["base_weight_kg"]
default_battery = profile["battery_wh"]
st.caption(f"Power System: `{profile['power_system']}`")
max_speed = profile["max_speed"]
max_altitude = profile["max_altitude"]
power_system = profile["power_system"]

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, max_value=1850.0, value=float(default_battery))
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, max_value=int(max_lift), value=int(max_lift * 0.5))
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, max_value=float(max_speed), value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=int(max_altitude), value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")
    submitted = st.form_submit_button("Estimate")

if submitted:
    try:
        total_weight_kg = base_weight_kg + (payload_weight_g / 1000)
        if temperature_c < 15:
            battery_capacity_wh *= 0.9
        elif temperature_c > 35:
            battery_capacity_wh *= 0.95

        air_density = max(0.6, 1.0 - 0.01 * (altitude_m / 100))
        hover_power = 170 * (total_weight_kg ** 1.5) / air_density

        if flight_mode == "Hover":
            total_power_draw = hover_power
        elif flight_mode == "Forward Flight":
            total_power_draw = hover_power * 1.15 + 0.02 * flight_speed_kmh**2 + 0.3 * wind_speed_kmh
        else:
            total_power_draw = hover_power * 1.25 + 0.022 * flight_speed_kmh**2 + 0.36 * wind_speed_kmh

        load_ratio = payload_weight_g / max_lift if max_lift > 0 else 0
        if load_ratio > 1.0:
            st.error("Simulation stopped: payload exceeds capacity.")
            st.stop()
        elif load_ratio > 0.9:
            efficiency_penalty = 1.25
        elif load_ratio > 0.7:
            efficiency_penalty = 1.1
        else:
            efficiency_penalty = 1.0

        if power_system == "Hybrid":
            base_draw = profile["draw_watt"]
            drag_factor = 1.0
            if flight_mode == "Forward Flight":
                drag_factor += 0.01 * flight_speed_kmh + 0.001 * (altitude_m / 100)
            elif flight_mode == "Waypoint Mission":
                drag_factor += 0.012 * flight_speed_kmh + 0.0012 * (altitude_m / 100)
            drag_factor *= 1.0 + 0.003 * total_weight_kg
            drag_factor = min(drag_factor, 2.2)
            total_draw = base_draw * drag_factor
        else:
            total_draw = total_power_draw * efficiency_penalty

        if elevation_gain_m > 0:
            battery_capacity_wh -= (total_weight_kg * 9.81 * elevation_gain_m) / 3600
        elif elevation_gain_m < 0:
            battery_capacity_wh += (total_weight_kg * 9.81 * abs(elevation_gain_m)) / 3600 * 0.2

        if simulate_failure and power_system == "Hybrid" and profile["crash_risk"]:
            if temperature_c > 35 or elevation_gain_m > 300 or (total_weight_kg > 100 and wind_speed_kmh > 20):
                st.error("SIMULATION FAILURE: Battery backup failure.")
                st.stop()

        if battery_capacity_wh <= 0:
            st.error("Simulation stopped: battery depleted.")
            st.stop()

        flight_time_minutes = (battery_capacity_wh / total_draw) * 60
        flight_time_minutes = min(flight_time_minutes, 120)

        st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

        st.subheader("AI Suggestions")
        if load_ratio > 1.0:
            st.warning("Payload exceeds lift. Reduce weight or use larger UAV.")
        elif load_ratio > 0.9:
            st.info("Close to max payload. Consider reducing for more endurance.")
        elif load_ratio < 0.5:
            st.info("Payload is light. You can carry more or optimize speed.")

        if flight_time_minutes < 10:
            st.warning("Short flight time. Try lowering payload or increasing battery size.")

        if total_draw > 1000:
            st.warning("Power draw is high. Ensure cooling systems are sufficient.")
        elif power_system == "Hybrid" and total_draw < 400:
            st.success("Hybrid draw is within stable operating range.")

    except Exception as e:
        st.error("Unexpected simulation error.")
        if debug_mode:
            st.exception(e)

st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")
