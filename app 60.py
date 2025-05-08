
import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

STATIC_MAX_LIFT_G = {
    "Generic Quad": 800,
    "DJI Phantom": 500,
    "RQ-11 Raven": 300,
    "RQ-20 Puma": 2500,
    "MQ-1 Predator": 600,
    "MQ-9 Reaper": 1700,
    "Skydio 2+": 600,
    "Freefly Alta 8": 9000,
    "Teal Golden Eagle": 3500,
    "Quantum Systems Vector": 1500
}

drone_model = st.selectbox("Drone Model", list(STATIC_MAX_LIFT_G.keys()) + ["Custom Build"])

if drone_model == "Custom Build":
    st.markdown("**Custom Lift Calculation:**")
    num_motors = st.number_input("Number of Motors", min_value=1, value=4, key="motors")
    thrust_per_motor = st.number_input("Thrust per Motor (g)", min_value=100, value=1000, key="thrust")
    frame_weight = 600
    battery_weight = 400
    max_lift = (num_motors * thrust_per_motor) - frame_weight - battery_weight
    if max_lift <= 0:
        st.error("Invalid configuration: calculated max payload is non-positive.")
        st.stop()
    st.caption(f"Calculated max payload capacity: {int(max_lift)} g")
else:
    max_lift = STATIC_MAX_LIFT_G[drone_model]
    frame_weight = 600
    battery_weight = 400
    st.caption(f"Maximum payload for this drone: {max_lift} g")

with st.form("uav_form"):
    st.subheader("Flight Parameters")

    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=50.0)
    default_payload = int(max_lift * 0.5)
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, value=default_payload)

    if payload_weight_g == max_lift:
        st.warning("Payload is at the maximum lift capacity. The drone may struggle to maintain stable flight.")

    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)

    if elevation_gain_m > 150 and drone_model != "Custom Build":
        st.warning("Warning: This elevation gain may exceed typical small UAV limits.")
    elif drone_model == "Custom Build" and elevation_gain_m > 250:
        st.warning("Custom build: verify thrust and power support for high-altitude climbs.")

    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])

    submitted = st.form_submit_button("Estimate")

if submitted:
    if payload_weight_g > max_lift:
        st.error("Payload exceeds lift capacity. The drone cannot take off with this configuration.")
        st.stop()

    # Apply temperature effect
    temp_penalty = 1.0
    if temperature_c < 15:
        temp_penalty = 0.9
    elif temperature_c > 35:
        temp_penalty = 0.95
    battery_capacity_wh *= temp_penalty
    st.caption(f"Adjusted for temperature: {temperature_c}°C → Effective capacity: {battery_capacity_wh:.1f} Wh")

    total_weight_g = frame_weight + battery_weight + payload_weight_g
    total_weight_kg = total_weight_g / 1000

    base_hover_efficiency = 170
    air_density_factor = max(0.6, 1.0 - 0.01 * (altitude_m / 100))
    hover_power = base_hover_efficiency * (total_weight_kg ** 1.5) / air_density_factor
    st.caption(f"Air density factor at {altitude_m} m: {air_density_factor:.2f}")

    if flight_mode == 'Hover':
        total_power_draw = hover_power
    elif flight_mode == 'Forward Flight':
        total_power_draw = hover_power * 1.15 + 0.02 * (flight_speed_kmh ** 2) + 0.3 * wind_speed_kmh
    elif flight_mode == 'Waypoint Mission':
        total_power_draw = hover_power * 1.25 + 0.022 * (flight_speed_kmh ** 2) + 0.36 * wind_speed_kmh

    load_ratio = payload_weight_g / max_lift
    if load_ratio < 0.7:
        efficiency_penalty = 1
    elif load_ratio < 0.9:
        efficiency_penalty = 1.1
    elif load_ratio <= 1.0:
        efficiency_penalty = 1.25
    else:
        efficiency_penalty = 1.4

    total_draw = total_power_draw * efficiency_penalty

    if elevation_gain_m > 0:
        climb_energy_j = total_weight_kg * 9.81 * elevation_gain_m
        climb_energy_wh = climb_energy_j / 3600
        battery_capacity_wh -= climb_energy_wh
        st.markdown(f"""**Climb Energy Cost:** `{climb_energy_wh:.2f} Wh`  
This accounts for lifting a {total_weight_kg:.2f} kg UAV to {elevation_gain_m} meters.""")
    elif elevation_gain_m < 0:
        descent_energy_j = total_weight_kg * 9.81 * abs(elevation_gain_m)
        recovered_wh = (descent_energy_j / 3600) * 0.2
        battery_capacity_wh += recovered_wh
        st.markdown(f"""**Descent Recovery Bonus:** `+{recovered_wh:.2f} Wh`  
Recovered from descending {abs(elevation_gain_m)} meters.""")

    if battery_capacity_wh <= 0:
        st.info("Simulation stopped: energy usage exceeded battery capacity.")
        st.stop()

    flight_time_minutes = (battery_capacity_wh / total_draw) * 60
    max_cap_minutes = min(battery_capacity_wh * 1.2, 120)
    if flight_time_minutes > max_cap_minutes:
        flight_time_minutes = max_cap_minutes

    st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")

    if flight_mode != "Hover":
        flight_distance_km = (flight_time_minutes / 60) * flight_speed_kmh
        st.metric("Estimated Max Distance", f"{flight_distance_km:.2f} km")

    st.subheader("AI Suggestions (Simulated GPT)")
    if payload_weight_g > max_lift * 0.7:
        st.write(f"**Tip**: Reduce payload to under {int(max_lift * 0.7)}g to increase endurance.")
    if wind_speed_kmh > 15:
        st.write("**Tip**: High wind may significantly reduce flight time—consider postponing.")
    if battery_capacity_wh < 30:
        st.write("**Tip**: Battery is under 30 Wh. Consider using a larger battery for extended missions.")
    if flight_speed_kmh > 40:
        st.write("**Tip**: High flight speed may be causing excessive aerodynamic drag. Consider slowing down.")
    if efficiency_penalty > 1.1:
        st.write("**Tip**: You're operating near max payload capacity. This significantly reduces efficiency.")
        required_energy_wh = total_draw * (flight_time_minutes / 60)
        if battery_capacity_wh < required_energy_wh * 1.1:
            suggested_wh = required_energy_wh * 1.2
            st.write(f"**Tip**: Estimated draw suggests a battery of at least {suggested_wh:.1f} Wh for safety margin.")

    # LIVE SIMULATION
    st.subheader("Live Simulation")
    time_step = 10
    total_steps = int(flight_time_minutes * 60 / time_step)
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
        gauge_text = "[" + "|" * bars + " " * (10 - bars) + f"] {battery_pct:.0f}%"
        gauge.markdown(f"**Battery Gauge:** `{gauge_text}`")

        timer.markdown(f"**Elapsed:** {time_elapsed} sec &nbsp;&nbsp;&nbsp; **Remaining:** {int(time_remaining)} sec")

        status.markdown(
            "**Battery Remaining:** {:.2f} Wh  \n**Power Draw:** {:.0f} W".format(
                battery_remaining, total_draw
            )
        )

        progress.progress(min(step / total_steps, 1.0))
        time.sleep(0.05)

    st.success("Simulation complete.")

st.caption("Demo project by Tareq Omrani | AI Engineering + UAV | 2025")
