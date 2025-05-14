import streamlit as st
import matplotlib.pyplot as plt
import time

GRAVITY = 9.81
TIME_STEP = 10

{
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
    "MQ-9 Reaper": {
        "max_payload_g": 1700000,
        "base_weight_kg": 2223,
        "power_system": "Hybrid",
        "draw_watt": 800,
        "battery_wh": 200,
        "crash_risk": True
    },
    "Freefly Alta 8": {
        "max_payload_g": 9000,
        "base_weight_kg": 6.2,
        "power_system": "Battery",
        "draw_watt": 400,
        "battery_wh": 710,
        "crash_risk": False
    }
}

def calculate_air_density_factor(altitude_m):
    return max(0.6, 1.0 - 0.01 * (altitude_m / 100))

def compute_power_draw(base_draw, power_system, flight_mode, speed_kmh):
    if power_system == "Hybrid":
        if flight_mode == "Climb":
            return base_draw * 1.25 + 0.01 * speed_kmh
        elif flight_mode == "Cruise":
            return base_draw * 1.0 + 0.005 * speed_kmh
        elif flight_mode == "Descent":
            return base_draw * 0.75
        return base_draw
    elif power_system == "Battery":
        if flight_mode == "Hover":
            return base_draw * 1.1
        elif flight_mode == "Waypoint":
            return base_draw * 1.15 + 0.02 * (speed_kmh ** 2)
        return base_draw + 0.02 * (speed_kmh ** 2)
    return base_draw

def apply_wind_drag(draw_watt, wind_speed_kmh, flight_speed_kmh, mode, enabled=True):
    if not enabled or mode == "Hover":
        return draw_watt
    relative_speed = flight_speed_kmh - wind_speed_kmh
    if relative_speed <= 0:
        return draw_watt * 1.25 + 0.03 * abs(relative_speed) ** 2
    elif wind_speed_kmh > 0:
        return draw_watt * 0.95 - 0.01 * wind_speed_kmh
    return draw_watt

def compute_elevation_effect(weight_kg, elevation_gain_m):
    if elevation_gain_m > 0:
        energy_j = weight_kg * GRAVITY * elevation_gain_m
        return -energy_j / 3600
    elif elevation_gain_m < 0:
        energy_j = weight_kg * GRAVITY * abs(elevation_gain_m)
        return (energy_j / 3600) * 0.2
    return 0

def simulate_mission_phases(phases, base_draw, power_system, battery_wh, weight_kg, wind_speed_kmh, wind_model, debug_mode):
    all_timestamps, all_battery_levels, all_draws = [], [], []
    total_elapsed = 0.0
    for phase in phases:
        name = phase["name"]
        duration_min = phase["duration_min"]
        speed_kmh = phase["speed_kmh"]
        elevation = phase["elevation_m"]
        draw = compute_power_draw(base_draw, power_system, name, speed_kmh)
        draw = apply_wind_drag(draw, wind_speed_kmh, speed_kmh, name, wind_model)
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

# --- Streamlit UI ---

st.set_page_config(page_title="UAV Full Estimator", layout="centered")
st.title("UAV Battery & Hybrid Mission Simulator")

profiles = UAV_PROFILES
debug_mode = st.checkbox("Enable Debug Mode")
model = st.selectbox("Select UAV", list(profiles.keys()))
profile = profiles[model]
max_payload = profile["max_payload_g"]
base_weight = profile["base_weight_kg"]

payload_g = st.slider("Payload (g)", 0, max_payload, int(max_payload * 0.5))
battery_wh = st.number_input("Battery Capacity (Wh)", 1.0, 2000.0, float(profile["battery_wh"]))
altitude_m = st.number_input("Flight Altitude (m)", 0, 5000, 500)
wind_kmh = st.number_input("Wind Speed (km/h)", 0.0, 100.0, 15.0)
temperature_c = st.number_input("Temperature (°C)", -20.0, 60.0, 25.0)
wind_model = st.checkbox("Enable Wind Drag", value=True)

st.markdown("## Mission Phases")
with st.form("mission_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        t_climb = st.number_input("Climb Duration (min)", 1, 60, 5)
        t_cruise = st.number_input("Cruise Duration (min)", 1, 180, 20)
        t_descent = st.number_input("Descent Duration (min)", 1, 60, 5)
    with col2:
        s_climb = st.number_input("Climb Speed (km/h)", 10, 300, 100)
        s_cruise = st.number_input("Cruise Speed (km/h)", 10, 300, 180)
        s_descent = st.number_input("Descent Speed (km/h)", 10, 300, 120)
    with col3:
        elev_climb = st.number_input("Elevation Gain (m)", 0, 5000, 400)
        elev_cruise = 0
        elev_descent = st.number_input("Elevation Loss (m)", 0, 5000, 400)

    submit = st.form_submit_button("Simulate Mission")

if submit:
    weight_kg = base_weight + (payload_g / 1000)
    if temperature_c < 15:
        battery_wh *= 0.9
    elif temperature_c > 35:
        battery_wh *= 0.95

    phases = [
        {"name": "Climb", "duration_min": t_climb, "speed_kmh": s_climb, "elevation_m": elev_climb},
        {"name": "Cruise", "duration_min": t_cruise, "speed_kmh": s_cruise, "elevation_m": elev_cruise},
        {"name": "Descent", "duration_min": t_descent, "speed_kmh": s_descent, "elevation_m": -elev_descent}
    ]

    times, levels, draws = simulate_mission_phases(
        phases, profile["draw_watt"], profile["power_system"],
        battery_wh, weight_kg, wind_kmh, wind_model, debug_mode
    )

    st.subheader("Battery Usage Over Time")
    fig, ax = plt.subplots()
    ax.plot(times, levels, label="Battery Remaining (Wh)")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Battery (Wh)")
    ax2 = ax.twinx()
    ax2.plot(times, draws, color='orange', linestyle='--', label="Power Draw (W)")
    ax2.set_ylabel("Power Draw (W)", color='orange')
    fig.legend(loc="upper right")
    st.pyplot(fig)
