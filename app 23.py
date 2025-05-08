import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

if "view" not in st.session_state:
    st.session_state.view = "Estimator"

view = st.radio("Select View", ["Estimator", "Simulate Flight"], index=0 if st.session_state.view == "Estimator" else 1)

if view == "Estimator":
    st.subheader("Flight Setup")
    st.session_state.flight_time = st.number_input("Estimated Flight Time (min)", min_value=1, value=20)
    st.session_state.battery_capacity = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=50.0)
    st.session_state.power_draw = st.number_input("Average Power Draw (W)", min_value=1.0, value=150.0)

    if st.button("Simulate Flight"):
        st.session_state.view = "Simulate Flight"
        st.experimental_rerun()

elif view == "Simulate Flight":
    st.subheader("Flight Simulation")
    st.success("Running with previous inputs.")

    flight_minutes = st.session_state.flight_time
    battery_wh = st.session_state.battery_capacity
    draw_w = st.session_state.power_draw

    time_step = 10
    total_steps = int(flight_minutes * 60 / time_step)
    battery_per_step = (draw_w * time_step) / 3600

    progress = st.progress(0)
    status = st.empty()
    gauge = st.empty()
    timer = st.empty()

    for step in range(total_steps + 1):
        time_elapsed = step * time_step
        battery_remaining = battery_wh - (step * battery_per_step)
        battery_pct = max(0, (battery_remaining / battery_wh) * 100)
        time_remaining = max(0, (flight_minutes * 60) - time_elapsed)

        # Build simple text-based battery gauge
        bars = int(battery_pct // 10)
        gauge_text = "[" + "|" * bars + " " * (10 - bars) + f"] {battery_pct:.0f}%"
        gauge.markdown(f"**Battery Gauge:** `{gauge_text}`")

        # Show elapsed and remaining time
        timer.markdown(f"**Elapsed:** {time_elapsed} sec &nbsp;&nbsp;&nbsp; **Remaining:** {int(time_remaining)} sec")

        # Telemetry block
        status.markdown(
            "**Battery Remaining:** {:.2f} Wh  
**Power Draw:** {:.0f} W".format(
                battery_remaining, draw_w
            )
        )

        progress.progress(min(step / total_steps, 1.0))
        time.sleep(0.05)

    st.success("Simulation complete.")