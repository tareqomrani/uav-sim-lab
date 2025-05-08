import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")

st.title("UAV Battery Efficiency Estimator")

# Trigger to show notice outside tab
show_notice = False

tab1, tab2 = st.tabs(["Estimator", "Simulate Flight"])

# Simulated data for testing
with tab1:
    st.subheader("Basic Estimator (Placeholder)")
    estimated_flight_time = st.number_input("Estimated Flight Time (min)", min_value=1, value=20)
    battery_capacity = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=50.0)
    power_draw = st.number_input("Average Power Draw (W)", min_value=1.0, value=150.0)
    simulate = st.button("Simulate Flight")
    if simulate:
        st.session_state.simulate_flight = True
        show_notice = True

# Notice section outside tab for visibility
if st.session_state.get("simulate_flight"):
    st.success("✅ Simulation started. Scroll down to view real-time telemetry updates.")

# Simulation section (safe and isolated)
with tab2:
    st.subheader("Flight Simulation Preview (Safe Prototype)")

    if st.session_state.get("simulate_flight"):
        st.write("**Simulation Running**")
        flight_minutes = estimated_flight_time
        battery_wh = battery_capacity
        draw_w = power_draw

        time_step = 10  # seconds per step
        total_steps = int(flight_minutes * 60 / time_step)
        battery_per_step = (draw_w * time_step) / 3600  # Wh

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