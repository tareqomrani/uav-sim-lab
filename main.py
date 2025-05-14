
import streamlit as st
import matplotlib.pyplot as plt
import time

# UAV Profiles
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

# UI Setup
st.set_page_config(page_title="UAV Estimator", layout="centered")
st.markdown("<h1 style='color:#39FF14;'>UAV Battery & Hybrid Simulation</h1>", unsafe_allow_html=True)

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Choose UAV", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

max_payload = profile["max_payload_g"]
default_payload = max_payload // 2 if max_payload > 0 else 0
payload = st.slider("Payload (g)", 0, max_payload if max_payload > 0 else 1, default_payload)

base_weight_kg = profile["base_weight_kg"]
st.caption(f"Base weight: {base_weight_kg:.2f} kg — Max payload: {max_payload} g")

# Add full parameter inputs
with st.form("mission_form"):
    battery_wh = st.number_input("Battery Capacity (Wh)", 1.0, 2000.0, float(profile["battery_wh"]))
    speed = st.number_input("Flight Speed (km/h)", 0.0, 200.0, 30.0)
    wind = st.number_input("Wind Speed (km/h)", 0.0, 100.0, 10.0)
    temp = st.number_input("Temperature (°C)", -20.0, 60.0, 25.0)
    alt = st.number_input("Altitude (m)", 0, 5000, 0)
    gain = st.number_input("Elevation Gain (m)", -1000, 1000, 0)
    mode = st.selectbox("Flight Mode", ["Hover", "Forward", "Waypoint"])
    sim_fail = st.checkbox("Enable Failure Sim")
    run = st.form_submit_button("Estimate")

if run:
    try:
        if payload > max_payload:
            st.error("Payload exceeds max lift.")
            st.stop()

        weight = base_weight_kg + (payload / 1000)
        adjusted_batt = battery_wh * (0.9 if temp < 15 else 0.95 if temp > 35 else 1.0)
        air_density = max(0.6, 1.0 - 0.01 * (alt / 100))

        base_draw = profile["draw_watt"]
        if profile["power_system"] == "Hybrid":
            draw = base_draw + 0.04 * (speed ** 2) + 30
        else:
            if mode == "Hover":
                draw = base_draw * 1.1
            elif mode == "Waypoint":
                draw = base_draw * 1.15 + 0.02 * (speed ** 2)
            else:
                draw = base_draw + 0.02 * (speed ** 2)

        if gain > 0:
            climb_j = weight * 9.81 * gain
            climb_wh = climb_j / 3600
            adjusted_batt -= climb_wh
            st.markdown(f"**Climb Cost:** `{climb_wh:.2f} Wh`")
        elif gain < 0:
            descent_j = weight * 9.81 * abs(gain)
            recovered = (descent_j / 3600) * 0.2
            adjusted_batt += recovered
            st.markdown(f"**Descent Recovery:** `+{recovered:.2f} Wh`")

        wind_drag = 1 + (wind / 100)
        draw *= wind_drag
        flight_min = (adjusted_batt / draw) * 60
        st.metric("Flight Time", f"{flight_min:.1f} min")

        if mode != "Hover":
            st.metric("Est. Distance", f"{(flight_min / 60) * speed:.2f} km")

        st.subheader("Simulation")
        step_sec = 10
        steps = max(1, int(flight_min * 60 / step_sec))
        draw_per_step = (draw * step_sec) / 3600
        timepoints = []
        battpoints = []
        status = st.empty()
        prog = st.progress(0)

        for step in range(steps + 1):
            elapsed = step * step_sec
            batt_left = adjusted_batt - step * draw_per_step
            pct = max(0, (batt_left / adjusted_batt) * 100)
            timepoints.append(elapsed)
            battpoints.append(max(batt_left, 0))
            status.markdown(f"**Battery Remaining:** {batt_left:.2f} Wh | **Draw:** {draw:.0f} W")
            prog.progress(min(step / steps, 1.0))
            time.sleep(0.02)

        fig, ax = plt.subplots()
        ax.plot(timepoints, battpoints)
        ax.set_title("Battery Use Over Time")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Battery (Wh)")
        st.pyplot(fig)

    except Exception as e:
        st.error("Simulation error.")
        if debug_mode:
            st.exception(e)
