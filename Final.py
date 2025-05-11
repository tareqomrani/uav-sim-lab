
import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

UAV_PROFILES = {
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 90, "battery_wh": 50, "crash_risk": False},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 180, "battery_wh": 275, "crash_risk": False},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "crash_risk": True}
}

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
battery_wh = st.number_input("Battery Capacity (Wh)", value=UAV_PROFILES[drone_model]["battery_wh"])
elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
temperature_c = st.number_input("Temperature (°C)", value=25.0)

if st.button("Estimate"):
    base_draw = UAV_PROFILES[drone_model]["draw_watt"]
    if UAV_PROFILES[drone_model]["power_system"] == "Battery":
        if flight_mode == "Hover":
            total_draw = base_draw * 1.1
        elif flight_mode == "Waypoint Mission":
            total_draw = base_draw * 1.15
        else:
            total_draw = base_draw
    else:
        total_draw = base_draw

    # temperature effect
    if temperature_c < 15:
        battery_wh *= 0.9
    elif temperature_c > 35:
        battery_wh *= 0.95

    # climb energy
    weight_kg = UAV_PROFILES[drone_model]["base_weight_kg"]
    if elevation_gain_m > 0:
        climb_energy_j = weight_kg * 9.81 * elevation_gain_m
        climb_energy_wh = climb_energy_j / 3600
        battery_wh -= climb_energy_wh
        st.markdown(f"**Climb Energy Cost:** `{climb_energy_wh:.2f} Wh`")
        if battery_wh <= 0:
            st.error("Simulation stopped: climb energy exceeds battery capacity.")
            st.stop()
    elif elevation_gain_m < 0:
        descent_energy_j = weight_kg * 9.81 * abs(elevation_gain_m)
        recovered_wh = (descent_energy_j / 3600) * 0.2
        battery_wh += recovered_wh
        st.markdown(f"**Descent Recovery Bonus:** `+{recovered_wh:.2f} Wh`")

    flight_time_min = (battery_wh / total_draw) * 60
    st.markdown(f"**Power Draw:** `{total_draw:.2f} W`")
    st.markdown(f"**Estimated Flight Time:** `{flight_time_min:.2f} minutes`")

    # Simulation
    st.subheader("Live Simulation")
    time_step = 10
    total_steps = max(1, int(flight_time_min * 60 / time_step))
    battery_per_step = (total_draw * time_step) / 3600
    progress = st.progress(0)
    status = st.empty()
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
        status.markdown(f"**Battery Remaining:** {battery_remaining:.2f} Wh  \n**Power Draw:** {total_draw:.0f} W")
        progress.progress(min(step / total_steps, 1.0))
        time.sleep(0.05)

    st.success("Simulation complete.")

    st.subheader("AI Suggestions (Simulated GPT)")
    if total_draw > base_draw:
        st.write("**Tip:** Hover or complex mission profiles consume more energy.")
    if battery_wh < 30:
        st.write("**Tip:** Battery is under 30 Wh. Consider using a larger battery.")
