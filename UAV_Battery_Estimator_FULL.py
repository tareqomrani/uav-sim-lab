import streamlit as st
import time

def calculate_hybrid_draw(total_draw_watts, power_system):
    if power_system.lower() == "hybrid":
        return total_draw_watts * 0.10
    return total_draw_watts

st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')
st.title('UAV Battery Efficiency Estimator')

UAV_PROFILES = {
    "MQ-1 Predator": {
        "max_payload_g": 204000,
        "base_weight_kg": 512,
        "power_system": "Hybrid",
        "draw_watt": 650,
        "battery_wh": 150,
        "fuel_capacity_liters": 665,
        "fuel_burn_lph": 120,
        "crash_risk": True,
        "ai_capabilities": "Semi-autonomous surveillance, pattern-of-life analysis"
    },
    "MQ-9 Reaper": {
        "max_payload_g": 1700000,
        "base_weight_kg": 2223,
        "power_system": "Hybrid",
        "draw_watt": 800,
        "battery_wh": 200,
        "fuel_capacity_liters": 1800,
        "fuel_burn_lph": 200,
        "crash_risk": True,
        "ai_capabilities": "Real-time threat detection, sensor fusion, autonomous target tracking"
    }
}

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

if "ai_capabilities" in profile:
    st.info(f"**AI Capabilities:** {profile['ai_capabilities']}")

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
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=100.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    submitted = st.form_submit_button("Estimate")

if submitted:
    try:
        if payload_weight_g > max_lift:
            st.error("Payload exceeds lift capacity.")
            st.stop()

        total_weight_kg = base_weight_kg + (payload_weight_g / 1000)
        if temperature_c < 15:
            battery_capacity_wh *= 0.9
        elif temperature_c > 35:
            battery_capacity_wh *= 0.95

        air_density_factor = max(0.6, 1.0 - 0.01 * (altitude_m / 100))
        st.caption(f"Air density factor at {altitude_m} m: {air_density_factor:.2f}")

        base_draw = profile["draw_watt"]
        total_draw = base_draw

        if elevation_gain_m > 0:
            climb_energy_j = total_weight_kg * 9.81 * elevation_gain_m
            climb_energy_wh = climb_energy_j / 3600
            battery_capacity_wh -= climb_energy_wh
            st.markdown(f"**Climb Energy Cost:** `{climb_energy_wh:.2f} Wh`")
            if battery_capacity_wh <= 0:
                st.error("Simulation stopped: climb energy exceeds battery capacity.")
                st.stop()
        elif elevation_gain_m < 0:
            descent_energy_j = total_weight_kg * 9.81 * abs(elevation_gain_m)
            recovered_wh = (descent_energy_j / 3600) * 0.2
            battery_capacity_wh += recovered_wh
            st.markdown(f"**Descent Recovery Bonus:** `+{recovered_wh:.2f} Wh`")

        battery_draw_only = calculate_hybrid_draw(total_draw, profile["power_system"])
        flight_time_battery_minutes = (battery_capacity_wh / battery_draw_only) * 60
        st.metric("Battery Flight Time", f"{flight_time_battery_minutes:.1f} minutes")

        if "fuel_capacity_liters" in profile and "fuel_burn_lph" in profile:
            fuel_hours = profile["fuel_capacity_liters"] / profile["fuel_burn_lph"]
            st.metric("Fuel Endurance", f"{fuel_hours:.2f} hours")

        st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")

    except Exception as e:
        st.error("Simulation error.")
        if debug_mode:
            st.exception(e)

