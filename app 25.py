import streamlit as st
import time

st.set_page_config(page_title="UAV Battery Efficiency Estimator", layout="centered")
st.title("UAV Battery Efficiency Estimator")

# Setup input fields
st.subheader("Flight Setup")

# Inputs for simulation
flight_minutes = st.number_input("Estimated Flight Time (min)", min_value=1, value=20)
battery_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, value=50.0)
payload_grams = st.number_input("Payload Weight (grams)", min_value=0, value=800)
flight_speed = st.number_input("Flight Speed (m/s)", min_value=0.0, value=10.0)

auto_calc = st.checkbox("Auto-calculate Average Power Draw", value=True)

if auto_calc:
    base_power = 80
    payload_factor = 0.1
    speed_factor = 5
    draw_w = base_power + (payload_grams * payload_factor) + (flight_speed * speed_factor)
    draw_w = round(draw_w, 2)
else:
    draw_w = st.number_input("Average Power Draw (W)", min_value=1.0, value=150.0)

st.markdown(f"**Estimated Power Draw:** `{draw_w} W`")

# Trigger simulation
if "run_sim" not in st.session_state:
    st.session_state.run_sim = False

if st.button("Simulate Flight"):
    st.session_state.run_sim = True

# Show simulation results if triggered
if st.session_state.run_sim:
    st.subheader("Flight Simulation")
    st.success("Simulation running with current parameters.")

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

        # Gauge
        bars = int(battery_pct // 10)
        gauge_text = "[" + "|" * bars + " " * (10 - bars) + f"] {battery_pct:.0f}%"
        gauge.markdown(f"**Battery Gauge:** `{gauge_text}`")

        # Time display
        timer.markdown(f"**Elapsed:** {time_elapsed} sec &nbsp;&nbsp;&nbsp; **Remaining:** {int(time_remaining)} sec")

        # Telemetry
        status.markdown(
            "**Battery Remaining:** {:.2f} Wh  
**Power Draw:** {:.0f} W".format(
                battery_remaining, draw_w
            )
        )

        progress.progress(min(step / total_steps, 1.0))
        time.sleep(0.05)

    st.success("Simulation complete.")