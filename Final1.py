import streamlit as st
import time

st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')
st.title('UAV Battery Efficiency Estimator')

UAV_PROFILES = {
    "Generic Quad": {
        "max_payload_g": 800,
        "base_weight_kg": 1.2,
        "power_system": "Battery",
        "draw_watt": 150,
        "battery_wh": 60,
        "crash_risk": False
    },
    "DJI Phantom": {
        "max_payload_g": 500,
        "base_weight_kg": 1.4,
        "power_system": "Battery",
        "draw_watt": 120,
        "battery_wh": 68,
        "crash_risk": False
    },
    "RQ-11 Raven": {
        "max_payload_g": 0,
        "base_weight_kg": 1.9,
        "power_system": "Battery",
        "draw_watt": 90,
        "battery_wh": 50,
        "crash_risk": False
    },
    "RQ-20 Puma": {
        "max_payload_g": 600,
        "base_weight_kg": 6.3,
        "power_system": "Battery",
        "draw_watt": 180,
        "battery_wh": 275,
        "crash_risk": False
    },
    "MQ-1 Predator": {
        "max_payload_g": 204000,
        "base_weight_kg": 512,
        "power_system": "Hybrid",
        "draw_watt": 650,
        "battery_wh": 150,
        "crash_risk": True
    },
    "MQ-9 Reaper": {
        "max_payload_g": 1700000,
        "base_weight_kg": 2223,
        "power_system": "Hybrid",
        "draw_watt": 800,
        "battery_wh": 200,
        "crash_risk": True
    },
    "Skydio 2+": {
        "max_payload_g": 150,
        "base_weight_kg": 0.8,
        "power_system": "Battery",
        "draw_watt": 90,
        "battery_wh": 45,
        "crash_risk": False
    },
    "Freefly Alta 8": {
        "max_payload_g": 9000,
        "base_weight_kg": 6.2,
        "power_system": "Battery",
        "draw_watt": 400,
        "battery_wh": 710,
        "crash_risk": False
    },
    "Teal Golden Eagle": {
        "max_payload_g": 2000,
        "base_weight_kg": 2.2,
        "power_system": "Hybrid",
        "draw_watt": 220,
        "battery_wh": 100,
        "crash_risk": True
    },
    "Quantum Systems Vector": {
        "max_payload_g": 1500,
        "base_weight_kg": 2.3,
        "power_system": "Battery",
        "draw_watt": 160,
        "battery_wh": 150,
        "crash_risk": False
    }
}


debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
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
        st.caption(f"Air density factor at {altitude_m} m: {air_density_factor:.2f}")

        base_draw = profile["draw_watt"]
        if profile["power_system"] == "Battery":
                    if flight_mode == "Hover":
                        total_draw = base_draw * 1.1
                    elif flight_mode == "Waypoint Mission":
                        total_draw = base_draw * 1.15 + 0.02 * (flight_speed_kmh ** 2)
                    else:
                        total_draw = base_draw + 0.02 * (flight_speed_kmh ** 2)
        else:
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

        flight_time_minutes = (battery_capacity_wh / total_draw) * 60
        st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

        st.subheader("AI Suggestions (Simulated GPT)")
        if payload_weight_g == max_lift:
            st.write("**Tip:** Payload is at maximum lift capacity. The drone may struggle to maintain stable flight.")
        if wind_speed_kmh > 15:
            st.write("**Tip:** High wind may significantly reduce flight time — consider postponing.")
        if battery_capacity_wh < 30:
            st.write("**Tip:** Battery is under 30 Wh. Consider using a larger battery.")
        if flight_mode in ["Hover", "Waypoint Mission"]:
            st.write("**Tip:** Hover and complex routes draw more power than forward cruise.")

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
            progress.progress(min(step / total_steps, 1.0))
            time.sleep(0.05)

        st.success("Simulation complete.")

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)

st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")
