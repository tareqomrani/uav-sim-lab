
import streamlit as st
import time
import matplotlib.pyplot as plt


<style>
.green { color: #00FF00; font-weight: bold; }
.red { color: #FF3333; font-weight: bold; }
.blue { color: #4169E1; font-weight: bold; }
</style>

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
    "RQ-11 Raven": {
        "max_payload_g": 0,
        "base_weight_kg": 1.9,
        "power_system": "Battery",
        "draw_watt": 90,
        "battery_wh": 50,
        "crash_risk": False
    },
    "MQ-9 Reaper": {
        "max_payload_g": 1700000,
        "base_weight_kg": 2223,
        "power_system": "Hybrid",
        "draw_watt": 800,
        "battery_wh": 200,
        "crash_risk": True
    }
}

debug = st.checkbox("Enable Debug Mode")
model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[model]

max_payload = profile["max_payload_g"]
base_weight = profile["base_weight_kg"]
power_system = profile["power_system"]
st.caption(f"Base weight: {base_weight:.2f} kg — Max payload: {max_payload} g")
st.markdown(f"<span class='blue'>Power system: {power_system}</span>", unsafe_allow_html=True)

default_batt = profile["battery_wh"]

with st.form("flight_form"):
    st.subheader("Flight Parameters")
    batt = st.number_input("Battery Capacity (Wh)", 1.0, 2000.0, value=float(default_batt))
    payload = st.number_input("Payload (g)", 0, value=int(max_payload * 0.5))
    speed = st.number_input("Speed (km/h)", 0.0, value=30.0)
    wind = st.number_input("Wind Speed (km/h)", 0.0, value=10.0)
    temp = st.number_input("Temperature (°C)", value=25.0)
    alt = st.number_input("Flight Altitude (m)", 0, 5000, value=0)
    gain = st.number_input("Elevation Gain (m)", -1000, 1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    submit = st.form_submit_button("Estimate")

if submit:
    try:
        if payload > max_payload:
            st.error("Payload exceeds lift capacity.")
            st.stop()

        weight = base_weight + (payload / 1000)

        # Battery temp effect
        if temp < 15:
            batt *= 0.9
        elif temp > 35:
            batt *= 0.95

        air_density = max(0.6, 1.0 - 0.01 * (alt / 100))
        st.markdown(f"<span class='green'>Air density factor at {alt} m: {air_density:.2f}</span>", unsafe_allow_html=True)

        hover_power = 170 * (weight ** 1.5) / air_density

        draw = profile["draw_watt"]
        if power_system == "Battery":
            if flight_mode == "Hover":
                draw = draw * 1.1
            elif flight_mode == "Waypoint Mission":
                draw = draw * 1.15 + 0.02 * (speed ** 2)
            else:
                draw = draw + 0.02 * (speed ** 2)

        if gain > 0:
            climb_j = weight * 9.81 * gain
            climb_wh = climb_j / 3600
            batt -= climb_wh
            st.markdown(f"<span class='red'>Climb Cost: {climb_wh:.2f} Wh</span>", unsafe_allow_html=True)
            if batt <= 0:
                st.error("Climb energy exceeds battery capacity.")
                st.stop()
        elif gain < 0:
            descent_j = weight * 9.81 * abs(gain)
            recovered = (descent_j / 3600) * 0.2
            batt += recovered
            st.markdown(f"<span class='green'>Descent Recovery: +{recovered:.2f} Wh</span>", unsafe_allow_html=True)

        wind_drag = 1 + (wind / 100)
        draw *= wind_drag

        flight_min = (batt / draw) * 60
        st.metric("Estimated Flight Time", f"{flight_min:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_min / 60) * speed:.2f} km")

        st.subheader("AI Suggestions (Simulated GPT)")
        if payload == max_payload:
            st.write("**Tip:** Payload is at max capacity. Expect strain.")
        if wind > 15:
            st.write("**Tip:** High wind may reduce flight time.")
        if batt < 30:
            st.write("**Tip:** Consider a higher capacity battery.")
        if flight_mode in ["Hover", "Waypoint Mission"]:
            st.write("**Tip:** This mode increases power consumption.")

        st.subheader("Live Simulation")
        step_sec = 10
        steps = max(1, int(flight_min * 60 / step_sec))
        draw_per_step = (draw * step_sec) / 3600
        prog = st.progress(0)
        status = st.empty()
        gauge = st.empty()
        timer = st.empty()
        timepoints, battpoints = [], []

        for step in range(steps + 1):
            elapsed = step * step_sec
            batt_left = batt - (step * draw_per_step)
            pct = max(0, (batt_left / batt) * 100)
            bars = int(pct // 10)
            gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {pct:.0f}%`")
            timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** {int((flight_min * 60) - elapsed)} sec")
            status.markdown(f"**Battery Remaining:** {batt_left:.2f} Wh  
**Power Draw:** {draw:.0f} W")
            prog.progress(min(step / steps, 1.0))
            timepoints.append(elapsed)
            battpoints.append(max(batt_left, 0))
            time.sleep(0.02)

        st.success("Simulation complete.")

        st.subheader("Battery Usage Graph")
        fig, ax = plt.subplots()
        ax.plot(timepoints, battpoints)
        ax.set_xlabel("Time (sec)")
        ax.set_ylabel("Battery (Wh)")
        ax.set_title("Battery Discharge Over Time")
        st.pyplot(fig)

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug:
            st.exception(e)

st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")

