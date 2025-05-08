import streamlit as st

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")

st.title("UAV Battery Efficiency Estimator")

STATIC_MAX_LIFT_G = {
    "Generic Quad": 800,
    "DJI Phantom": 500
}

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    drone_model = st.selectbox("Drone Model", list(STATIC_MAX_LIFT_G.keys()) + ["Custom Build"])

    if drone_model == "Custom Build":
        st.markdown("**Custom Lift Calculation:**")
        num_motors = st.number_input("Number of Motors", min_value=1, value=4)
        thrust_per_motor = st.number_input("Thrust per Motor (g)", min_value=100, value=1000)
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

    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=50.0)
    default_payload = int(max_lift * 0.5)
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, value=default_payload)

    if payload_weight_g == max_lift:
        st.warning("Payload is at the maximum lift capacity. The drone may struggle to maintain stable flight.")

    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])

    submitted = st.form_submit_button("Estimate")

if submitted:
    if payload_weight_g > max_lift:
        st.error("Payload exceeds lift capacity. The drone cannot take off with this configuration.")
        st.stop()

    total_weight_g = frame_weight + battery_weight + payload_weight_g
    total_weight_kg = total_weight_g / 1000

    base_hover_efficiency = 170
    hover_power = base_hover_efficiency * (total_weight_kg ** 1.5)

    drag_factor = 0.01
    drag_draw = drag_factor * (flight_speed_kmh ** 2) if flight_mode != "Hover" else 0
    wind_penalty = 0.3 * wind_speed_kmh

    load_ratio = payload_weight_g / max_lift
    if load_ratio < 0.7:
        efficiency_penalty = 1
    elif load_ratio < 0.9:
        efficiency_penalty = 1.1
    elif load_ratio <= 1.0:
        efficiency_penalty = 1.25
    else:
        efficiency_penalty = 1.4

    total_draw = (hover_power + drag_draw + wind_penalty) * efficiency_penalty
    flight_time_minutes = (battery_capacity_wh / total_draw) * 60
    max_reasonable_minutes = 45
    if flight_time_minutes > max_reasonable_minutes:
        flight_time_minutes = max_reasonable_minutes

    st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")

    if flight_mode != "Hover":
        flight_distance_km = (flight_time_minutes / 60) * flight_speed_kmh
        st.metric("Estimated Max Distance", f"{flight_distance_km:.2f} km")

    st.subheader("AI Suggestions (Simulated GPT)")
    if payload_weight_g > 800:
        st.write("**Tip**: Reduce payload to under 800g to increase endurance.")
    if wind_speed_kmh > 15:
        st.write("**Tip**: High wind may significantly reduce flight time—consider postponing.")
    if battery_capacity_wh < 30:
        st.write("**Tip**: Increase battery size or reduce mission length.")
    if drag_draw > 10:
        st.write("**Tip**: High flight speed may be causing excessive aerodynamic drag. Consider slowing down.")
    if efficiency_penalty > 1.1:
        st.write("**Tip**: You're operating near max payload capacity. This significantly reduces efficiency.")

st.caption("Demo project by Tareq Omrani | AI Engineering + UAV | 2025")