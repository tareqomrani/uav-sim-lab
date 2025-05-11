import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 170, "battery_wh": 60, "crash_risk": False, "max_speed_kmh": 80, "max_altitude_m": 2000},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 180, "battery_wh": 68, "crash_risk": False, "max_speed_kmh": 72, "max_altitude_m": 6000},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 100, "battery_wh": 50, "crash_risk": False, "max_speed_kmh": 90, "max_altitude_m": 4500},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 250, "battery_wh": 275, "crash_risk": False, "max_speed_kmh": 80, "max_altitude_m": 3000},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 900, "battery_wh": 150, "crash_risk": True, "max_speed_kmh": 217, "max_altitude_m": 7500},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 1100, "battery_wh": 200, "crash_risk": True, "max_speed_kmh": 300, "max_altitude_m": 15000},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 130, "battery_wh": 45, "crash_risk": False, "max_speed_kmh": 58, "max_altitude_m": 4000},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 450, "battery_wh": 710, "crash_risk": False, "max_speed_kmh": 72, "max_altitude_m": 2500},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 300, "battery_wh": 100, "crash_risk": True, "max_speed_kmh": 93, "max_altitude_m": 5000},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 240, "battery_wh": 150, "crash_risk": False, "max_speed_kmh": 72, "max_altitude_m": 3000}
}

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()) + ["Custom Build"])
st.markdown("*Full UI loaded. Simulation logic executes after pressing Estimate.*")

with st.form("uav_form"):
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
        max_speed_kmh = 100
        max_altitude_m = 5000
    else:
        profile = UAV_PROFILES[drone_model]
        max_lift = profile["max_payload_g"]
        base_weight_kg = profile["base_weight_kg"]
        default_battery = profile["battery_wh"]
        max_speed_kmh = profile["max_speed_kmh"]
        max_altitude_m = profile["max_altitude_m"]
        st.caption(f"Base weight: {base_weight_kg:.2f} kg — Max payload: {max_lift} g")
        st.caption(f"Power system: `{profile['power_system']}`")

    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=float(default_battery))
    default_payload = int(max_lift * 0.5)
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, max_value=int(max_lift), value=default_payload)
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, max_value=float(max_speed_kmh), value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0.0, max_value=float(max_altitude_m), value=0.0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")

    submitted = st.form_submit_button("Estimate")

if submitted:
    st.success("Form submitted successfully. Simulation logic would go here.")



    try:
        if max_lift == 0 and payload_weight_g > 0:
            st.error("SIMULATION STOPPED: This UAV cannot carry payload.")
            st.stop()

        total_weight_kg = base_weight_kg + (payload_weight_g / 1000)
        temp_penalty = 0.9 if temperature_c < 15 else 0.95 if temperature_c > 35 else 1.0
        battery_capacity_wh *= temp_penalty

        air_density_factor = max(0.6, 1.0 - 0.01 * (altitude_m / 100))
        hover_eff = 170
        hover_power = hover_eff * (total_weight_kg ** 1.5) / air_density_factor

        if flight_mode == 'Hover':
            total_power_draw = hover_power
        elif flight_mode == 'Forward Flight':
            total_power_draw = hover_power * 1.15 + 0.02 * (flight_speed_kmh ** 2) + 0.3 * wind_speed_kmh
        else:
            total_power_draw = hover_power * 1.25 + 0.022 * (flight_speed_kmh ** 2) + 0.36 * wind_speed_kmh

        load_ratio = payload_weight_g / max_lift if max_lift > 0 else 0
        eff_penalty = 1.0
        if 0.7 <= load_ratio < 0.9: eff_penalty = 1.1
        elif 0.9 <= load_ratio <= 1.0: eff_penalty = 1.25
        elif load_ratio > 1.0: eff_penalty = 1.4

        if drone_model != "Custom Build" and UAV_PROFILES[drone_model]["power_system"] == "Hybrid":
            base_draw = UAV_PROFILES[drone_model]["draw_watt"]
            drag_factor = 1.0 + 0.01 * flight_speed_kmh + 0.001 * (altitude_m / 100)
            drag_factor *= 1.0 + 0.003 * total_weight_kg
            drag_factor = min(drag_factor, 2.2)
            total_draw = base_draw * drag_factor

            st.subheader("Hybrid Draw Insights")
            st.markdown(f'''
- **Base Draw:** {base_draw:.0f} W  
- **Speed Factor:** `{flight_speed_kmh} km/h`  
- **Altitude Factor:** `{altitude_m} m`  
- **Weight Factor:** `{total_weight_kg:.1f} kg`  
- **Total Adjusted Draw:** **{total_draw:.0f} W**
''')
        else:
            total_draw = total_power_draw * eff_penalty

        if elevation_gain_m > 0:
            battery_capacity_wh -= (total_weight_kg * 9.81 * elevation_gain_m) / 3600
        elif elevation_gain_m < 0:
            battery_capacity_wh += ((total_weight_kg * 9.81 * abs(elevation_gain_m)) / 3600) * 0.2

        if simulate_failure and UAV_PROFILES[drone_model]["power_system"] == "Hybrid" and UAV_PROFILES[drone_model]["crash_risk"]:
            if temperature_c > 35 or elevation_gain_m > 300 or (total_weight_kg > 100 and wind_speed_kmh > 20):
                st.error("SIMULATION FAILURE: Backup battery failure triggered.")
                st.stop()

        if battery_capacity_wh <= 0:
            st.info("Simulation stopped: energy depleted.")
            st.stop()

        flight_time_minutes = (battery_capacity_wh / total_draw) * 60
        flight_time_minutes = min(flight_time_minutes, 120)

        if UAV_PROFILES[drone_model]["power_system"] == "Hybrid":
            safe_min = total_draw * (10 / 60)
            if battery_capacity_wh < safe_min:
                st.warning(f"Battery may be too small. Recommend at least {safe_min:.0f} Wh for 10 min operation.")

        st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

        st.subheader("Live Simulation")
        steps = max(1, int(flight_time_minutes * 6))
        step_time = 10
        draw_rate = total_draw * step_time / 3600
        progress = st.progress(0)
        status = st.empty()
        gauge = st.empty()
        timer = st.empty()

        for step in range(steps + 1):
            t = step * step_time
            remaining = battery_capacity_wh - step * draw_rate
            pct = max(0, (remaining / battery_capacity_wh) * 100)
            eta = max(0, (flight_time_minutes * 60) - t)
            bars = int(pct // 10)
            gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {pct:.0f}%`")
            timer.markdown(f"**Elapsed:** {t} sec **Remaining:** {int(eta)} sec")
            status.markdown(f"**Battery Remaining:** {remaining:.2f} Wh  \n**Power Draw:** {total_draw:.0f} W")
            progress.progress(min(step / steps, 1.0))
            time.sleep(0.01)

        st.success("Simulation complete.")

    except Exception as e:
        st.error("Unexpected simulation error.")
        if debug_mode:
            st.exception(e)


st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")
