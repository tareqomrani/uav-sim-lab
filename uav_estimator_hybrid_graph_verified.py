
import streamlit as st
import matplotlib.pyplot as plt
import time

# Constants
GRAVITY = 9.81  # m/s²
TIME_STEP = 10  # seconds for simulation animation

# UAV Profiles
@st.cache_data
def load_uav_profiles():
    return {
        "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 150, "battery_wh": 60, "crash_risk": False},
        "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 120, "battery_wh": 68, "crash_risk": False},
        "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 90, "battery_wh": 50, "crash_risk": False},
        "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 180, "battery_wh": 275, "crash_risk": False},
        "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 650, "battery_wh": 150, "crash_risk": True},
        "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "crash_risk": True},
        "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 90, "battery_wh": 45, "crash_risk": False},
        "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 400, "battery_wh": 710, "crash_risk": False},
        "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Hybrid", "draw_watt": 220, "battery_wh": 100, "crash_risk": True},
        "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 160, "battery_wh": 150, "crash_risk": False}
    }

def calculate_air_density_factor(altitude_m):
    return max(0.6, 1.0 - 0.01 * (altitude_m / 100))


def hybrid_power_model(base_draw, phase, speed_kmh):
    if phase == "Climb":
        return base_draw * 1.25 + 0.01 * speed_kmh
    elif phase == "Cruise":
        return base_draw * 1.0 + 0.005 * speed_kmh
    elif phase == "Descent":
        return base_draw * 0.75
    return base_draw

def compute_power_draw(base_draw, power_system, flight_mode, speed_kmh):
    if power_system == "Hybrid":
        if flight_mode == "Waypoint Mission":
            return hybrid_power_model(base_draw, "Climb", speed_kmh)
        elif flight_mode == "Forward Flight":
            return hybrid_power_model(base_draw, "Cruise", speed_kmh)
        elif flight_mode == "Hover":
            return hybrid_power_model(base_draw, "Descent", speed_kmh)
        return base_draw

    if power_system != "Battery":
        return base_draw
    if flight_mode == "Hover":
        return base_draw * 1.1
    elif flight_mode == "Waypoint Mission":
        return base_draw * 1.15 + 0.02 * (speed_kmh ** 2)
    return base_draw + 0.02 * (speed_kmh ** 2)

def apply_wind_drag(draw_watt, wind_speed_kmh, flight_speed_kmh, flight_mode, enabled=True):
    if not enabled or flight_mode == "Hover":
        return draw_watt
    relative_speed = flight_speed_kmh - wind_speed_kmh
    if relative_speed <= 0:
        return draw_watt * 1.25 + 0.03 * abs(relative_speed) ** 2
    elif wind_speed_kmh > 0:
        return draw_watt * 0.95 - 0.01 * wind_speed_kmh
    return draw_watt

def simulate_battery_drain(flight_time_min, total_draw, battery_wh, enable_animation=True):
    total_secs = flight_time_min * 60
    steps = max(1, int(total_secs / TIME_STEP))
    per_step_wh = (total_draw * TIME_STEP) / 3600
    progress = st.progress(0)
    status = st.empty()
    gauge = st.empty()
    timer = st.empty()

    timestamps, battery_levels, draw_profile = [], [], []
    
    for step in range(steps + 1):
        elapsed = step * TIME_STEP
        used = per_step_wh * step
        remaining = max(0.1, battery_wh - used)
        battery_pct = max(0, min(100, (remaining / battery_wh) * 100))
        bars = int(battery_pct // 10)
        timestamps.append(elapsed / 60)
        battery_levels.append(remaining)
        draw_profile.append(total_draw)
        gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {battery_pct:.0f}%`")
        timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** {int(total_secs - elapsed)} sec")
        status.markdown(f"**Battery Remaining:** {remaining:.2f} Wh  \n**Power Draw:** {total_draw:.0f} W")
        progress.progress(min(step / steps, 1.0))
        if enable_animation:
            time.sleep(0.05)

        # Track for chart
        timestamps.append(elapsed / 60)
        battery_levels.append(remaining); draw_profile.append(total_draw)

        gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {battery_pct:.0f}%`")
        timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** {int(total_secs - elapsed)} sec")
        status.markdown(f"**Battery Remaining:** {remaining:.2f} Wh  \n**Power Draw:** {total_draw:.0f} W")
**Power Draw:** {total_draw:.0f} W")
        progress.progress(min(step / steps, 1.0))
        if enable_animation:
            time.sleep(0.05)

    st.success("Simulation complete.")

    # Plot battery usage and draw profile
    st.subheader("Battery Usage Over Time")
    fig, ax = plt.subplots()
    ax.plot(timestamps, battery_levels, label="Battery Remaining (Wh)")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Battery (Wh)")
    ax.set_title("Battery Usage Simulation")
    ax.grid(True)
    ax2 = ax.twinx()
    ax2.plot(timestamps, draw_profile, color='orange', linestyle='--', label='Power Draw (W)')
    ax2.set_ylabel("Power Draw (W)", color='orange')
    fig.legend(loc="upper right")
    st.pyplot(fig)

def calculate_flight_time(battery_wh, draw_watt):
    draw_watt = max(draw_watt, 0.1)
    return (battery_wh / draw_watt) * 60

def compute_elevation_effect(weight_kg, elevation_gain_m):
    if elevation_gain_m > 0:
        energy_j = weight_kg * GRAVITY * elevation_gain_m
        return -energy_j / 3600
    elif elevation_gain_m < 0:
        energy_j = weight_kg * GRAVITY * abs(elevation_gain_m)
        return (energy_j / 3600) * 0.2
    return 0

# UI Start
st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')
st.title('UAV Battery Efficiency Estimator')
debug_mode = st.checkbox("Enable Debug Mode")
profiles = load_uav_profiles()
drone_model = st.selectbox("Drone Model", list(profiles.keys()))
profile = profiles[drone_model]
max_lift = profile["max_payload_g"]
base_weight_kg = profile["base_weight_kg"]
st.caption(f"Base weight: {base_weight_kg:.2f} kg — Max payload: {max_lift} g")
st.caption(f"Power system: `{profile['power_system']}`")

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, max_value=1850.0, value=float(profile["battery_wh"]))
    payload_weight_g = st.slider("Payload Weight (g)", 0, max_lift, int(max_lift * 0.5))
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    wind_effects_enabled = st.checkbox("Enable Wind Drag Modeling", value=True)
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")
    submitted = st.form_submit_button("Estimate")

if submitted:
    try:
        if payload_weight_g > max_lift:
            st.error("Payload exceeds lift capacity. The drone cannot take off.")
        else:
            total_weight_kg = base_weight_kg + (payload_weight_g / 1000)

            if temperature_c < 15:
                battery_capacity_wh *= 0.9
            elif temperature_c > 35:
                battery_capacity_wh *= 0.95

            density = calculate_air_density_factor(altitude_m)
            st.caption(f"Air density factor at {altitude_m} m: {density:.2f}")
            draw = compute_power_draw(profile["draw_watt"], profile["power_system"], flight_mode, flight_speed_kmh)
            draw = apply_wind_drag(draw, wind_speed_kmh, flight_speed_kmh, flight_mode, wind_effects_enabled)

            battery_capacity_wh += compute_elevation_effect(total_weight_kg, elevation_gain_m)
            battery_capacity_wh = max(battery_capacity_wh, 0.1)

            flight_minutes = calculate_flight_time(battery_capacity_wh, draw)
            st.metric("Estimated Flight Time", f"{flight_minutes:.1f} minutes")
            if flight_mode != "Hover":
                distance_km = (flight_minutes / 60) * flight_speed_kmh
                st.metric("Estimated Max Distance", f"{distance_km:.2f} km")

            st.subheader("AI Suggestions (Simulated GPT)")
            if payload_weight_g == max_lift:
                st.write("**Tip:** Max payload may reduce stability.")
            if wind_speed_kmh > 15:
                st.write("**Tip:** High wind may reduce efficiency.")
            if battery_capacity_wh < 30:
                st.write("**Tip:** Battery below 30 Wh. Consider upgrading.")
            if flight_mode in ["Hover", "Waypoint Mission"]:
                st.write("**Tip:** These modes consume more energy.")

            st.subheader("Live Simulation")
            simulate_battery_drain(flight_minutes, draw, battery_capacity_wh)

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)

st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")


# Multi-phase simulation logic

def simulate_mission_phases(phases, base_draw, power_system, battery_wh, weight_kg, wind_speed_kmh, wind_model, debug_mode):
    all_timestamps, all_battery_levels, all_draws = [], [], []
    total_elapsed = 0.0

    for phase in phases:
        name = phase["name"]
        duration_min = phase["duration_min"]
        speed_kmh = phase["speed_kmh"]
        elevation = phase["elevation_m"]

        # Determine draw
        if power_system == "Hybrid":
            draw = hybrid_power_model(base_draw, name, speed_kmh)
        else:
            draw = compute_power_draw(base_draw, power_system, name, speed_kmh)

        draw = apply_wind_drag(draw, wind_speed_kmh, speed_kmh, name, wind_model)

        # Elevation energy impact
        battery_wh += compute_elevation_effect(weight_kg, elevation)
        battery_wh = max(battery_wh, 0.1)

        total_secs = duration_min * 60
        steps = max(1, int(total_secs / TIME_STEP))
        per_step_wh = (draw * TIME_STEP) / 3600

        for step in range(steps + 1):
        elapsed = total_elapsed + step * TIME_STEP
        used = per_step_wh * step
        remaining = max(0.1, battery_wh - used)
        all_timestamps.append(elapsed / 60)
        all_battery_levels.append(remaining)
        all_draws.append(draw)

        total_elapsed += total_secs
        battery_wh -= per_step_wh * steps
        if debug_mode:
            print(f"Phase: {name} | Draw: {draw:.1f} W | Battery: {battery_wh:.1f} Wh")

    return all_timestamps, all_battery_levels, all_draws


# === Multi-Phase Mission UI Integration ===
if profile["power_system"] == "Hybrid":
    st.subheader("Multi-Phase Mission Planning")
    with st.form("mission_form"):
        st.markdown("### Define Mission Phases")

        col1, col2, col3 = st.columns(3)
        with col1:
            climb_time = st.number_input("Climb Duration (min)", 1, 60, 5)
            cruise_time = st.number_input("Cruise Duration (min)", 1, 120, 15)
            descent_time = st.number_input("Descent Duration (min)", 1, 60, 5)
        with col2:
            climb_speed = st.number_input("Climb Speed (km/h)", 10, 200, 80)
            cruise_speed = st.number_input("Cruise Speed (km/h)", 10, 200, 120)
            descent_speed = st.number_input("Descent Speed (km/h)", 10, 200, 90)
        with col3:
            climb_elev = st.number_input("Climb Elevation Gain (m)", 0, 5000, 300)
            cruise_elev = 0
            descent_elev = st.number_input("Descent Elevation Loss (m)", 0, 5000, 300)

        simulate_mission = st.form_submit_button("Run Multi-Phase Mission")

    if simulate_mission:
        try:
            weight_kg = base_weight_kg + (payload_weight_g / 1000)
            if temperature_c < 15:
                battery_capacity_wh *= 0.9
            elif temperature_c > 35:
                battery_capacity_wh *= 0.95

            mission_phases = [
                {"name": "Climb", "duration_min": climb_time, "speed_kmh": climb_speed, "elevation_m": climb_elev},
                {"name": "Cruise", "duration_min": cruise_time, "speed_kmh": cruise_speed, "elevation_m": cruise_elev},
                {"name": "Descent", "duration_min": descent_time, "speed_kmh": descent_speed, "elevation_m": -descent_elev}
            ]

            timestamps, battery_levels, draw_profile = simulate_mission_phases(
                mission_phases,
                profile["draw_watt"],
                profile["power_system"],
                battery_capacity_wh,
                weight_kg,
                wind_speed_kmh,
                wind_effects_enabled,
                debug_mode
            )

            st.subheader("Multi-Phase Mission Battery Chart")
            fig, ax = plt.subplots()
            ax.plot(timestamps, battery_levels, label="Battery Remaining (Wh)")
            ax.set_xlabel("Time (minutes)")
            ax.set_ylabel("Battery (Wh)")
            ax.set_title("Battery Usage in Multi-Phase Flight")
            ax.grid(True)

            ax2 = ax.twinx()
            ax2.plot(timestamps, draw_profile, color='orange', linestyle='--', label='Power Draw (W)')
            ax2.set_ylabel("Power Draw (W)", color='orange')
            fig.legend(loc="upper right")
            st.pyplot(fig)

        except Exception as e:
            st.error("Multi-phase mission simulation failed.")
            if debug_mode:
                st.exception(e)


# === Custom Digital Colors Styling ===
st.markdown("""
<style>
.digital-green {
    color: #00FF00;
    font-weight: bold;
}
.royal-blue {
    color: #4169E1;
    font-weight: bold;
}
.alert-red {
    color: #FF4444;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# === Example Use ===
st.markdown('<p class="digital-green">DIGITAL GREEN STATUS: OK</p>', unsafe_allow_html=True)
st.markdown('<p class="royal-blue">ROYAL BLUE NOTE: Cruise is optimal.</p>', unsafe_allow_html=True)
st.markdown('<p class="alert-red">ALERT RED WARNING: Battery below threshold.</p>', unsafe_allow_html=True)
