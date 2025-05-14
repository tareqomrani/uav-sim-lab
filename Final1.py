
import streamlit as st

st.set_page_config(page_title="UAV Battery Estimator", layout="centered")

st.title("UAV Battery Efficiency Estimator")

# Sample UAV profile
profile = {
    "name": "RQ-11 Raven",
    "base_weight_kg": 1.9,
    "power_system": "Battery",
    "base_draw_w": 100,
    "max_payload_g": 0,
    "battery_wh": 100
}

# Display model info
st.markdown(f"<span style='color:#4169E1;'>Base weight: {profile['base_weight_kg']} kg</span>", unsafe_allow_html=True)
st.markdown(f"<span style='color:#4169E1;'>Power System: {profile['power_system']}</span>", unsafe_allow_html=True)
st.markdown(f"<span style='color:#4169E1;'>Base draw: {profile['base_draw_w']} W</span>", unsafe_allow_html=True)

# Payload section
if profile["max_payload_g"] > 0:
    payload_slider = st.slider("Payload Weight (g)", 0, profile["max_payload_g"], int(profile["max_payload_g"] * 0.5), key="payload_slider")
    payload = st.number_input("Payload (g)", min_value=0, max_value=profile["max_payload_g"], value=payload_slider, key="payload_input")
else:
    st.markdown("<span style='color:#FFA500;'>Note: This model does not support payloads.</span>", unsafe_allow_html=True)
    payload = 0

# Temperature input
temperature = st.number_input("Temperature (°C)", min_value=-10, max_value=45, value=25, key="temp_input")

# Flight Speed input
speed_slider = st.slider("Flight Speed (km/h)", 10, 150, 40, key="speed_slider")
speed = st.number_input("Flight Speed (km/h)", min_value=10, max_value=150, value=speed_slider, key="speed_input")

# Wind Speed input
wind_slider = st.slider("Wind Speed (km/h)", 0, 100, 10, key="wind_slider")
wind_speed = st.number_input("Wind Speed (km/h)", min_value=0, max_value=100, value=wind_slider, key="wind_input")

# Estimate button
if st.button("🔋 Estimate", key="estimate_button"):
    wind_factor = 1 + (wind_speed / 100) * 0.1
    adjusted_draw = profile["base_draw_w"] * wind_factor
    st.success(f"Estimated adjusted draw: {adjusted_draw:.2f} W")

# Footer
st.markdown("<br><hr><center style='color:#4169E1;'>Built by Tareq Omrani &copy; UAV Battery Efficiency Estimator 2025</center>", unsafe_allow_html=True)
