
import streamlit as st
import time

def calculate_hybrid_draw(total_draw_watts, power_system):
    if power_system.lower() == "hybrid":
        return total_draw_watts * 0.10
    return total_draw_watts

def adjust_draw_for_wind(total_draw, flight_speed_kmh, wind_speed_kmh):
    relative_speed = flight_speed_kmh + wind_speed_kmh  # Headwind only
    drag_multiplier = 1 + 0.01 * (relative_speed ** 2) / 100
    return total_draw * drag_multiplier

st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')
st.title('UAV Battery Efficiency Estimator')

UAV_PROFILES = {
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 650, "battery_wh": 150, "crash_risk": True, "ai_capabilities": "Semi-autonomous surveillance, pattern-of-life analysis"},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "crash_risk": True, "ai_capabilities": "Real-time threat detection, sensor fusion, autonomous target tracking"},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 220, "battery_wh": 100, "crash_risk": True, "ai_capabilities": "AI-driven ISR, edge-based visual classification, GPS-denied flight"},
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
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    submitted = st.form_submit_button("Estimate")

if submitted:
    try:
        if payload_weight_g > max_lift:
            st.error("Payload exceeds lift capacity. The drone cannot take off with this configuration.")
            st.stop()

        total_weight_kg = base_weight_kg + (payload_weight_g / 1000)
        weight_factor = total_weight_kg / base_weight_kg

        if temperature_c < 15:
            battery_capacity_wh *= 0.9
        elif temperature_c > 35:
            battery_capacity_wh *= 0.95

        air_density_factor = max(0.6, 1.0 - 0.01 * (altitude_m / 100))
        st.caption(f"Air density factor at {altitude_m} m: {air_density_factor:.2f}")

        base_draw = profile["draw_watt"]
        if flight_mode == "Hover":
            total_draw = base_draw * 1.1
        elif flight_mode == "Waypoint Mission":
            total_draw = base_draw * 1.15 + 0.02 * (flight_speed_kmh ** 2)
        else:
            total_draw = base_draw + 0.02 * (flight_speed_kmh ** 2)

        total_draw *= weight_factor
        total_draw *= 1 / air_density_factor
        total_draw = adjust_draw_for_wind(total_draw, flight_speed_kmh, wind_speed_kmh)

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

        if battery_capacity_wh < 30:
            st.write("**Tip:** Battery is under 30 Wh. Consider using a larger battery.")

        battery_draw_only = calculate_hybrid_draw(total_draw, profile["power_system"])

        if battery_draw_only <= 0:
            st.error('Simulation failed: Battery draw is zero or undefined.')
            st.stop()

        flight_time_minutes = (battery_capacity_wh / battery_draw_only) * 60
        st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

        st.success("Calculation complete.")

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)

    st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")
