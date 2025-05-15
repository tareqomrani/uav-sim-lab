
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
        "crash_risk": True,
        "ai_capabilities": "Semi-autonomous surveillance, pattern-of-life analysis"
    }
}

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

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
        if profile["power_system"] == "Battery":
            if flight_mode == "Hover":
                total_draw = base_draw * 1.1
            elif flight_mode == "Waypoint Mission":
                total_draw = base_draw * 1.15 + 0.02 * (flight_speed_kmh ** 2)
            else:
                total_draw = base_draw + 0.02 * (flight_speed_kmh ** 2)

        wind_drag_watt = 0.1 * wind_speed_kmh
        total_draw += wind_drag_watt

        if elevation_gain_m > 0:
            climb_energy_j = total_weight_kg * 9.81 * elevation_gain_m
            climb_energy_wh = climb_energy_j / 3600
            battery_capacity_wh -= climb_energy_wh
            st.markdown(f"**Climb Energy Cost:** `{climb_energy_wh:.2f} Wh`")
            if battery_capacity_wh <= 0:
                st.error("Simulation stopped: climb energy exceeds battery capacity.")
                st.stop()

        battery_draw_only = calculate_hybrid_draw(total_draw, profile["power_system"])
        if battery_draw_only <= 0:
            st.error('Simulation failed: Battery draw is zero or undefined.')
            st.stop()

        flight_time_minutes = (battery_capacity_wh / battery_draw_only) * 60
        st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

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
            if battery_remaining <= 0:
                battery_remaining = 0
                battery_pct = 0
                bars = 0
                gauge.markdown(f"**Battery Gauge:** `[{' ' * 10}] 0%`")
                timer.markdown(f"**Elapsed:** {time_elapsed} sec **Remaining:** 0 sec")
                status.markdown(f"**Battery Remaining:** 0.00 Wh  **Power Draw:** {total_draw:.0f} W")
                progress.progress(1.0)
                break
            battery_pct = max(0, (battery_remaining / battery_capacity_wh) * 100)
            time_remaining = max(0, (flight_time_minutes * 60) - time_elapsed)
            bars = int(battery_pct // 10)
            gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {battery_pct:.0f}%`")
            timer.markdown(f"**Elapsed:** {time_elapsed} sec **Remaining:** {int(time_remaining)} sec")
            status.markdown(f"**Battery Remaining:** {battery_remaining:.2f} Wh  **Power Draw:** {total_draw:.0f} W")
            progress.progress(min(step / total_steps, 1.0))
            time.sleep(0.05)

        st.success("Simulation complete.")

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)

    st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")


