
import streamlit as st
import math

# Model database
models = {
    "RQ-11 Raven": {
        "ai": "None",
        "base_weight_kg": 1.9,
        "power_system": "Battery",
        "base_draw_w": 100,
        "max_payload_g": 0,
        "battery_wh": 200
    },
    "Hybrid X": {
        "ai": "Obstacle Avoidance, Autonomous Navigation",
        "base_weight_kg": 3.0,
        "power_system": "Hybrid",
        "base_draw_w": 150,
        "max_payload_g": 1500,
        "battery_wh": 500
    }
}

st.set_page_config(layout="centered", page_title="UAV Battery Estimator", page_icon="✈️")

st.title("UAV Battery Efficiency Estimator")

model = st.selectbox("Select UAV Model", list(models.keys()))
profile = models[model]

st.markdown(f"**AI Capabilities:** `{profile['ai']}`")
st.markdown(f"<span style='color:#4169E1;'>Power System: {profile['power_system']}</span>", unsafe_allow_html=True)
st.markdown(f"<span style='color:#4169E1;'>Base draw: {profile['base_draw_w']} W</span>", unsafe_allow_html=True)

# Payload section
if profile["max_payload_g"] > 0:
    payload_slider = st.slider("Payload Weight (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5), key=f"payload_slider_{model}")
    payload = st.number_input("Payload (g)", min_value=0, max_value=profile["max_payload_g"], value=payload_slider, key=f"payload_input_{model}")
else:
    st.markdown("<span style='color:#FFA500;'>Note: This model does not support payloads.</span>", unsafe_allow_html=True)
    payload = 0

# Input section
temperature = st.number_input("Temperature (°C)", -10, 45, 25, key=f"temp_input_{model}")
speed_slider = st.slider("Flight Speed (km/h)", 10, 150, 40, key=f"speed_slider_{model}")
speed = st.number_input("Flight Speed (km/h)", 10, 150, speed_slider, key=f"speed_input_{model}")
wind_slider = st.slider("Wind Speed (km/h)", 0, 100, 10, key=f"wind_slider_{model}")
wind_speed = st.number_input("Wind Speed (km/h)", 0, 100, wind_slider, key=f"wind_input_{model}")

# Mission Profile
st.markdown("<h5 style='color:#4169E1;'>Mission Profile (Time-Based)</h5>", unsafe_allow_html=True)
climb_time = st.slider("Climb Time (min)", 0, 30, 3, key=f"climb_slider_{model}")
cruise_time = st.slider("Cruise Time (min)", 0, 60, 10, key=f"cruise_slider_{model}")
descent_time = st.slider("Descent Time (min)", 0, 30, 2, key=f"descend_slider_{model}")

# Estimate Button
if st.button("🔋 Estimate", key=f"estimate_button_{model}"):
    total_time_min = climb_time + cruise_time + descent_time
    wind_factor = 1 + (wind_speed / 100) * 0.1
    air_density_factor = 1 - ((temperature - 15) * 0.01)

    if profile["power_system"] == "Hybrid":
        hybrid_modifier = 1.2 if speed > 60 else 1.0
    else:
        hybrid_modifier = 1.0

    base_draw = profile["base_draw_w"] * hybrid_modifier * air_density_factor * wind_factor
    climb_draw = base_draw * 1.5
    cruise_draw = base_draw * 1.0
    descent_draw = base_draw * 0.6

    climb_energy = climb_draw * climb_time
    cruise_energy = cruise_draw * cruise_time
    descent_energy = descent_draw * descent_time

    payload_penalty = 1 + (payload / 1000) * 0.1
    total_energy = (climb_energy + cruise_energy + descent_energy) * payload_penalty

    battery_wh = profile["battery_wh"]
    estimated_time = (battery_wh * 60) / total_energy if total_energy else 0

    st.success(f"Estimated flight time: {estimated_time:.1f} minutes")

    if estimated_time < 5:
        st.warning("Warning: Very short estimated time. Consider reducing payload or increasing battery capacity.")

# Footer
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center;color:#4169E1;'>Built by Tareq Omrani © UAV Battery Efficiency Estimator 2025</div>", unsafe_allow_html=True)
o
