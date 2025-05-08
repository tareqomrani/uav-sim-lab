import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

# Initialize tab state
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Estimator"

# Simulate tab behavior with a radio selector
tab_choice = st.radio("Navigate", ["Estimator", "Simulate Flight"], index=0 if st.session_state.active_tab == "Estimator" else 1)

# Flight inputs (only visible in Estimator mode)
if tab_choice == "Estimator":
    st.subheader("Flight Setup")
    estimated_flight_time = st.number_input("Estimated Flight Time (min)", min_value=1, value=20, key="flight_time")
    battery_capacity = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=50.0, key="battery_capacity")
    power_draw = st.number_input("Average Power Draw (W)", min_value=1.0, value=150.0, key="power_draw")

    if st.button("Simulate Flight"):
        st.session_state.active_tab = "Simulate Flight"
        st.rerun()

# Simulation panel
if tab_choice == "Simulate Flight":
    st.subheader("Flight Simulation Preview")
    st.success("Simulation running with the parameters from Estimator.")

    flight_minutes = st.session_state.get("flight_time", 20)
    battery_wh = st.session_state.get("battery_capacity", 50.0)
    draw_w = st.session_state.get("power_draw", 150.0)

    time_step = 10
    total_steps = int(flight_minutes * 60 / time_step)
    battery_per_step = (draw_w * time_step) / 3600

    progress = st.progress(0)
    status = st.empty()

    for step in range(total_steps + 1):
        time_elapsed = step * time_step
        battery_remaining = battery_wh - (step * battery_per_step)
        battery_pct = max(0, (battery_remaining / battery_wh) * 100)

        status.markdown(
            "**Time Elapsed:** {} sec  \n**Battery Remaining:** {:.2f} Wh ({:.0f}%)  \n**Power Draw:** {:.0f} W".format(
                time_elapsed, battery_remaining, battery_pct, draw_w
            )
        )
        progress.progress(min(step / total_steps, 1.0))
        time.sleep(0.05)

    st.success("Simulation complete.")