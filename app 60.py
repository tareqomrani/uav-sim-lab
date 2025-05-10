import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 170, "battery_wh": 60, "crash_risk": False},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 180, "battery_wh": 68, "crash_risk": False},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 100, "battery_wh": 50, "crash_risk": False},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 250, "battery_wh": 275, "crash_risk": False},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 900, "battery_wh": 150, "crash_risk": True},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 1100, "battery_wh": 200, "crash_risk": True},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 130, "battery_wh": 45, "crash_risk": False},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 450, "battery_wh": 710, "crash_risk": False},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 300, "battery_wh": 100, "crash_risk": True},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 240, "battery_wh": 150, "crash_risk": False}
}

debug_mode = st.checkbox("Enable Debug Mode")

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()) + ["Custom Build"])

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
else:
    profile = UAV_PROFILES[drone_model]
    max_lift = profile["max_payload_g"]
    base_weight_kg = profile["base_weight_kg"]
    st.caption(f"Base weight: {base_weight_kg:.2f} kg — Max payload: {max_lift} g")
    st.caption(f"Power system: `{profile['power_system']}`")
    default_battery = profile["battery_wh"]

with st.form("uav_form"):
    st.subheader("Flight Parameters")

    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=default_battery)
    default_payload = int(max_lift * 0.5)
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, max_value=int(max_lift), value=default_payload)

    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)

    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")

    submitted = st.form_submit_button("Estimate")
         import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 170, "battery_wh": 60, "crash_risk": False},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 180, "battery_wh": 68, "crash_risk": False},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 100, "battery_wh": 50, "crash_risk": False},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 250, "battery_wh": 275, "crash_risk": False},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 900, "battery_wh": 150, "crash_risk": True},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 1100, "battery_wh": 200, "crash_risk": True},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 130, "battery_wh": 45, "crash_risk": False},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 450, "battery_wh": 710, "crash_risk": False},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 300, "battery_wh": 100, "crash_risk": True},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 240, "battery_wh": 150, "crash_risk": False}
}

debug_mode = st.checkbox("Enable Debug Mode")

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()) + ["Custom Build"])

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
else:
    profile = UAV_PROFILES[drone_model]
    max_lift = profile["max_payload_g"]
    base_weight_kg = profile["base_weight_kg"]
    st.caption(f"Base weight: {base_weight_kg:.2f} kg — Max payload: {max_lift} g")
    st.caption(f"Power system: `{profile['power_system']}`")
    default_battery = profile["battery_wh"]

with st.form("uav_form"):
    st.subheader("Flight Parameters")

    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=default_battery)
    default_payload = int(max_lift * 0.5)
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, max_value=int(max_lift), value=default_payload)

    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)

    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")

    submitted = st.form_submit_button("Estimate")
    
