import streamlit as st
import matplotlib.pyplot as plt
import time

# UAV Profiles
UAV_PROFILES = {
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

# UI and Setup
st.set_page_config(page_title="UAV Battery Simulator", layout="centered")
st.title("UAV Battery & Hybrid Simulator")

GRAVITY = 9.81
TIME_STEP = 10

def compute_elevation_effect(weight_kg, elevation_m):
    if elevation_m > 0:
        return -(weight_kg * GRAVITY * elevation_m) / 3600
    elif elevation_m < 0:
        return ((weight_kg * GRAVITY * abs(elevation_m)) / 3600) * 0.2
    return 0

def compute_power_draw(base_draw, power_system, phase, speed_kmh):
    if power_system == "Hybrid":
        if phase == "Climb":
            return base_draw * 1.25 + 0.01 * speed_kmh
        elif phase == "Cruise":
            return base_draw + 0.005 * speed_kmh
        elif phase == "Descent":
            return base_draw * 0.75
    return base_draw + 0.02 * (speed_kmh ** 2)

drone_model = st.selectbox("Choose UAV Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

payload = st.slider("Payload (g)", 0, profile["max_payload_g"], profile["max_payload_g"] // 2)
altitude = st.number_input("Flight Altitude (m)", 0, 5000, 500)
wind_speed = st.number_input("Wind Speed (km/h)", 0.0, 100.0, 15.0)
temperature = st.number_input("Temperature (°C)", -20.0, 60.0, 25.0)
battery_capacity = st.number_input("Battery Capacity (Wh)", 1.0, 2000.0, float(profile["battery_wh"]))

with st.form("mission"):
    st.subheader("Mission Parameters")
    climb_t = st.number_input("Climb Time (min)", 1, 30, 5)
    cruise_t = st.number_input("Cruise Time (min)", 1, 120, 20)
    descent_t = st.number_input("Descent Time (min)", 1, 30, 5)
    climb_v = st.number_input("Climb Speed (km/h)", 10, 200, 80)
    cruise_v = st.number_input("Cruise Speed (km/h)", 10, 300, 150)
    descent_v = st.number_input("Descent Speed (km/h)", 10, 200, 100)
    elev_gain = st.number_input("Elevation Gain (m)", 0, 2000, 300)
    elev_loss = st.number_input("Elevation Loss (m)", 0, 2000, 300)
    simulate = st.form_submit_button("Run Simulation")

if simulate:
    weight = profile["base_weight_kg"] + (payload / 1000)
    battery = battery_capacity
    if temperature < 15:
        battery *= 0.9
    elif temperature > 35:
        battery *= 0.95

    phases = [
        ("Climb", climb_t, climb_v, elev_gain),
        ("Cruise", cruise_t, cruise_v, 0),
        ("Descent", descent_t, descent_v, -elev_loss)
    ]

    times, battery_levels, draws = [], [], []
    elapsed = 0
    for phase, duration, speed, elev in phases:
        draw = compute_power_draw(profile["draw_watt"], profile["power_system"], phase, speed)
        battery += compute_elevation_effect(weight, elev)
        steps = int(duration * 60 / TIME_STEP)
        for step in range(steps + 1):
            t = elapsed + step * TIME_STEP
            used = draw * TIME_STEP / 3600
            battery = max(0.1, battery - used)
            times.append(t / 60)
            battery_levels.append(battery)
            draws.append(draw)
        elapsed += duration * 60

    st.subheader("Battery Simulation Results")
    fig, ax = plt.subplots()
    ax.plot(times, battery_levels, label="Battery (Wh)")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Battery (Wh)")
    ax2 = ax.twinx()
    ax2.plot(times, draws, color='orange', linestyle='--', label="Power Draw (W)")
    ax2.set_ylabel("Power Draw (W)")
    fig.legend(loc="upper right")
    st.pyplot(fig)
