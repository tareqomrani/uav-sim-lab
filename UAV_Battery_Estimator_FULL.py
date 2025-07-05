from datetime import datetime
import pytz

# Timestamp for display and logging
eastern = pytz.timezone("US/Eastern")
now = datetime.now(eastern)
timestamp = now.strftime("v%Y%m%d_%H%M%S")

# UAV Battery Efficiency Estimator — Enhanced Version
# Built by Tareq Omrani | Timestamp: v20250704_185946

import streamlit as st
import time
import math

# === Constants ===
SIGMA = 5.670374419e-8  # Stefan–Boltzmann constant
SEA_LEVEL_DENSITY = 1.225  # kg/m^3

# === Utility Functions ===

def get_air_density(altitude_m):
    # Barometric formula approximation
    sea_level_temp = 288.15  # K
    lapse_rate = 0.0065  # K/m
    g = 9.80665  # m/s²
    R = 287.05  # J/kg/K

    temp = sea_level_temp - lapse_rate * altitude_m
    exponent = g / (R * lapse_rate)
    return SEA_LEVEL_DENSITY * (temp / sea_level_temp) ** exponent

def calculate_hybrid_draw(total_draw_watts, power_system, hybrid_battery_share=0.15):
    if power_system.lower() == "hybrid":
        return total_draw_watts * hybrid_battery_share
    return total_draw_watts

def calculate_fuel_consumption(power_draw_watt, duration_hr, max_power=800, base_burn_rate_lph=1.5):
    # Dynamic burn based on % of max rated power
    usage_ratio = min(power_draw_watt / max_power, 1.0)
    return base_burn_rate_lph * usage_ratio * duration_hr

def estimate_thermal_signature(draw_watt, efficiency, surface_area, emissivity, ambient_temp_C):
    waste_heat = draw_watt * (1 - efficiency)
    if waste_heat <= 0 or surface_area <= 0 or emissivity <= 0:
        return 0
    temp_K = (waste_heat / (emissivity * SIGMA * surface_area)) ** 0.25
    temp_C = temp_K - 273.15
    delta_T = max(0.1, min(temp_C - ambient_temp_C, 40.0))  # clamp to 0.1–40°C
    return round(delta_T, 1)

def thermal_risk_rating(delta_T):
    if delta_T < 10:
        return "Low"
    elif delta_T < 20:
        return "Moderate"
    else:
        return "High"

def insert_thermal_and_fuel_outputs(total_draw, profile, flight_time_minutes, temperature_c, ir_shielding, delta_T):
    st.subheader("Thermal Signature & Fuel Analysis")
    risk = thermal_risk_rating(delta_T)
    st.metric(label="Thermal Signature Risk", value=f"{risk} (ΔT = {delta_T:.1f}°C)")
    if profile["power_system"].lower() == "hybrid":
        fuel_burned = calculate_fuel_consumption(
            power_draw_watt=total_draw,
            duration_hr=flight_time_minutes / 60
        )
        st.metric(label="Estimated Fuel Used", value=f"{fuel_burned:.2f} L")
    else:
        st.info("Fuel tracking not applicable for battery-powered UAVs.")

# === UI Setup ===

st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')
st.markdown("<h1 style='color:#00FF00;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)

UAV_PROFILES = {
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "crash_risk": True, "ai_capabilities": "Target tracking, sensor fusion, loiter AI"},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 650, "battery_wh": 150, "crash_risk": True, "ai_capabilities": "Surveillance, pattern-of-life analysis"},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 180, "battery_wh": 275, "crash_risk": False, "ai_capabilities": "ISR mission planning, autonomous loiter"},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 90, "battery_wh": 50, "crash_risk": False, "ai_capabilities": "Auto-stabilized route flight"},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Battery", "draw_watt": 220, "battery_wh": 100, "crash_risk": True, "ai_capabilities": "Edge ISR, GPS-denied nav"},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 90, "battery_wh": 45, "crash_risk": False, "ai_capabilities": "Obstacle avoidance, SLAM"},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 160, "battery_wh": 150, "crash_risk": False, "ai_capabilities": "Autonomous AI route learning"},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 400, "battery_wh": 710, "crash_risk": False, "ai_capabilities": "Camera coordination, stable hover"},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 120, "battery_wh": 68, "crash_risk": False, "ai_capabilities": "Mapping, object tracking"},
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 150, "battery_wh": 60, "crash_risk": False, "ai_capabilities": "Basic waypoint flight"},
    "Custom Build": {"max_payload_g": 1500, "base_weight_kg": 2.0, "power_system": "Battery", "draw_watt": 180, "battery_wh": 150, "crash_risk": False, "ai_capabilities": "User-defined components"}
}

st.caption(f"GPT-UAV Planner | Enhanced Version | {timestamp}")

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

if "ai_capabilities" in profile:
    st.info(f"**AI Capabilities:** {profile['ai_capabilities']}")

max_lift = profile["max_payload_g"]
base_weight_kg = profile["base_weight_kg"]
st.caption(f"Base weight: {base_weight_kg:.2f} kg — Max payload: {max_lift} g")
st.caption(f"Power system: `{profile['power_system']}`")
default_battery = profile["battery_wh"]

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, max_value=1850.0, value=float(default_battery))
    default_payload = int(max_lift * 0.5)
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, value=default_payload)
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Ambient Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    cloud_cover = st.slider("Cloud Cover (%)", 0, 100, 50)
    gustiness = st.slider("Wind Gust Factor (0 = calm, 10 = extreme)", 0, 10, 2)
    terrain_penalty = st.slider("Terrain Complexity", 1.0, 1.5, 1.1)
    stealth_drag_penalty = st.slider("Stealth Loadout Drag Factor", 1.0, 1.5, 1.0)
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")
    submitted = st.form_submit_button("Estimate")

if submitted:
    try:
        if payload_weight_g > max_lift:
            st.error("Payload exceeds lift capacity.")
            st.stop()

        total_weight_kg = base_weight_kg + (payload_weight_g / 1000)
        if temperature_c < 15:
            battery_capacity_wh *= 0.9
        elif temperature_c > 35:
            battery_capacity_wh *= 0.95

        air_density = get_air_density(altitude_m)
        density_ratio = air_density / SEA_LEVEL_DENSITY
        st.caption(f"Air density at {altitude_m} m: {air_density:.3f} kg/m³ (ratio: {density_ratio:.2f})")

        base_draw = profile["draw_watt"]
        weight_factor = total_weight_kg / base_weight_kg
        wind_drag_factor = 1 + (wind_speed_kmh / 100)

        if profile["power_system"] == "Battery":
            if flight_mode == "Hover":
                total_draw = base_draw * 1.1 * weight_factor
            elif flight_mode == "Waypoint Mission":
                total_draw = (base_draw * 1.15 + 0.02 * (flight_speed_kmh ** 2)) * wind_drag_factor
            else:
                total_draw = (base_draw + 0.02 * (flight_speed_kmh ** 2)) * wind_drag_factor
        else:
            total_draw = base_draw * weight_factor

        total_draw *= terrain_penalty * stealth_drag_penalty * density_ratio

        if gustiness > 0:
            gust_penalty = 1 + (gustiness * 0.015)
            total_draw *= gust_penalty
            st.markdown(f"**Wind Turbulence Penalty:** `{(gust_penalty - 1)*100:.1f}%` added draw")

        ir_shielding = 1 - (cloud_cover / 100) * 0.5

        if elevation_gain_m > 0:
            climb_energy_j = total_weight_kg * 9.81 * elevation_gain_m
            climb_energy_wh = climb_energy_j / 3600
            battery_capacity_wh -= climb_energy_wh
            st.markdown(f"**Climb Energy Cost:** `{climb_energy_wh:.2f} Wh`")
            if battery_capacity_wh <= 0:
                st.error("Simulation stopped: climb energy exceeds battery capacity.")
                st.stop()
        elif elevation_gain_m < 0:
            descent_energy_j = total_weight_kg * 9.81 * abs(elevation_gain_m)
            recovered_wh = (descent_energy_j / 3600) * 0.2
            battery_capacity_wh += recovered_wh
            st.markdown(f"**Descent Recovery Bonus:** `+{recovered_wh:.2f} Wh`")

        battery_draw_only = calculate_hybrid_draw(total_draw, profile["power_system"])
# === Apply Mission Legs to Energy Estimation ===
        if mission_legs > 0 and mission_distances and mission_altitudes:
            leg_energy_wh_total = 0
            total_km = 0
            current_alt = altitude_m  # starting altitude
            for i in range(mission_legs):
                dist_km = mission_distances[i]
                target_alt = mission_altitudes[i]
                delta_alt = target_alt - current_alt
                time_hr = dist_km / max(flight_speed_kmh, 1e-5)
                leg_draw = total_draw
                # Add climb or descent cost
                if delta_alt > 0:
                    climb_j = total_weight_kg * 9.81 * delta_alt
                    climb_wh = climb_j / 3600
                    leg_energy_wh_total += climb_wh
                elif delta_alt < 0:
                    descent_j = total_weight_kg * 9.81 * abs(delta_alt)
                    recovered_wh = (descent_j / 3600) * 0.2
                    leg_energy_wh_total -= recovered_wh  # energy saved
                # Add cruising power usage
                cruise_energy_wh = leg_draw * time_hr
                leg_energy_wh_total += cruise_energy_wh
                total_km += dist_km
                current_alt = target_alt
            battery_capacity_wh -= leg_energy_wh_total
            st.markdown(f"**Mission Plan Energy Cost:** `{leg_energy_wh_total:.2f} Wh` over {total_km:.1f} km")
            if battery_capacity_wh <= 0:
                st.error("Mission plan exceeds battery capacity.")
                st.stop()
        delta_T = estimate_thermal_signature(draw_watt=total_draw, efficiency=0.85, surface_area=0.3, emissivity=0.9, ambient_temp_C=temperature_c)
        delta_T *= ir_shielding

        if battery_draw_only <= 0:
            st.error("Simulation failed: Battery draw is zero or undefined.")
            st.stop()

        flight_time_minutes = (battery_capacity_wh / battery_draw_only) * 60
        st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
        if flight_mode != "Hover":
            st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

        insert_thermal_and_fuel_outputs(
            total_draw=total_draw,
            profile=profile,
            flight_time_minutes=flight_time_minutes,
            temperature_c=temperature_c,
            ir_shielding=ir_shielding,
            delta_T=delta_T
        )

        st.subheader("Live Battery Simulation")
        time_step = 10
        total_steps = max(1, int(flight_time_minutes * 60 / time_step))
        battery_per_step = (total_draw * time_step) / 3600
        progress = st.progress(0)
        status = st.empty()
        gauge = st.empty()
        timer = st.empty()

        for step in range(total_steps + 1):
            time_elapsed = step * time_step
            battery_remaining = battery_capacity_wh - (step * battery_per_step)
            if battery_remaining <= 0:
                battery_remaining = 0
                battery_pct = 0
                bars = 0
                gauge.markdown(f"**Battery Gauge:** `[{' ' * 10}] 0%`")
                timer.markdown(f"**Elapsed:** {time_elapsed} sec **Remaining:** 0 sec")
                status.markdown(f"**Battery Remaining:** 0.00 Wh  **Power Draw:** {total_draw:.0f} W")
                progress.progress(1.0)
                break
            battery_pct = max(0, (battery_remaining / battery_capacity_wh) * 100)
            time_remaining = max(0, (flight_time_minutes * 60) - time_elapsed)
            bars = int(battery_pct // 10)
            gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {battery_pct:.0f}%`")
            timer.markdown(f"**Elapsed:** {time_elapsed} sec **Remaining:** {int(time_remaining)} sec")
            status.markdown(f"**Battery Remaining:** {battery_remaining:.2f} Wh  **Power Draw:** {total_draw:.0f} W")
            progress.progress(min(step / total_steps, 1.0))
            time.sleep(0.05)

        st.success("Simulation complete.")

        if simulate_failure or (profile["power_system"].lower() == "hybrid" or delta_T > 15 or altitude_m > 100):
            st.warning("**Threat Alert:** UAV may be visible to AI-based IR or radar systems.")
        else:
            st.success("**Safe:** UAV remains below typical detection thresholds.")

        # AI Tips (not real AI)
        st.subheader("AI-Inspired Tips")
        if payload_weight_g == max_lift:
            st.write("**Tip:** Payload is at maximum lift capacity.")
        if wind_speed_kmh > 15:
            st.write("**Tip:** High wind may reduce flight time.")
        if battery_capacity_wh < 30:
            st.write("**Tip:** Battery under 30 Wh. Consider a larger pack.")
        if flight_mode in ["Hover", "Waypoint Mission"]:
            st.write("**Tip:** Hover and waypoint modes use more power.")
        if stealth_drag_penalty > 1.2:
            st.write("**Tip:** Stealth loadout may reduce endurance.")
        if delta_T > 15:
            st.write("**Tip:** Thermal load high. Reduce weight or fly lower.")
        if altitude_m > 100:
            st.write("**Tip:** Altitudes above 100m increase detection risk.")
        if gustiness >= 5:
            st.write("**Tip:** Gust factor >5 may destabilize light UAVs.")

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)

st.caption("GPT-UAV Planner | Enhanced by OpenAI | 2025")

import json
import matplotlib.pyplot as plt

# === Mission Planning ===
# === Mission Planning ===
# === Mission Planning ===
# === Mission Planning ===
with st.expander("📍 Mission Planning (Experimental)"):
    mission_legs = st.slider("Number of Mission Legs", 1, 5, 1, key="mission_legs_slider_main")
    mission_distances = []
    mission_altitudes = []
    for i in range(mission_legs):
        dist = st.number_input(f"Distance for Leg {{i+1}} (km)", min_value=0.1, value=2.0, key=f"dist_leg_{{i}}")
        alt = st.number_input(f"Altitude for Leg {{i+1}} (m)", min_value=0, value=100, key=f"alt_leg_{{i}}")
        mission_distances.append(dist)
        mission_altitudes.append(alt)
    mission_legs = st.slider("Number of Mission Legs", 1, 5, 1, key="mission_legs_slider_main")
    mission_distances = []
    mission_altitudes = []
    for i in range(mission_legs):
        dist = st.number_input(f"Distance for Leg {i+1} (km)", min_value=0.1, value=2.0, key=f"mission_dist_{i}"))
        alt = st.number_input(f"Altitude for Leg {i+1} (m)", min_value=0, value=100, key=f"mission_alt_{i}"))
        mission_distances.append(dist)
        mission_altitudes.append(alt)
        mission_legs = st.slider("Number of Mission Legs", 1, 5, 1, key="mission_legs_slider_main")
        mission_distances = []
        mission_altitudes = []
        for i in range(mission_legs):
            dist = st.number_input(f"Distance for Leg {i+1} (km)", min_value=0.1, value=2.0, key=f"mission_dist_{i}"))
            alt = st.number_input(f"Altitude for Leg {i+1} (m)", min_value=0, value=100, key=f"mission_alt_{i}"))
            mission_distances.append(dist)
            mission_altitudes.append(alt)
        if st.button("Estimate Mission Plan"):
            total_km = sum(mission_distances)
            avg_alt = sum(mission_altitudes) / len(mission_altitudes)
            st.write(f"Total planned distance: **{total_km:.2f} km**")
            st.write(f"Average flight altitude: **{avg_alt:.0f} m**")
            st.write("Leg breakdown:")
            for i, (d, a) in enumerate(zip(mission_distances, mission_altitudes)):
                st.write(f"• Leg {i+1}: {d:.2f} km at {a} m")
    mission_legs = st.slider("Number of Mission Legs", 1, 5, 1, key="mission_legs_slider_main")
    mission_distances = []
    mission_altitudes = []
    for i in range(mission_legs):
        dist = st.number_input(f"Distance for Leg {i+1} (km)", min_value=0.1, value=2.0, key=f"mission_dist_{i}"))
        alt = st.number_input(f"Altitude for Leg {i+1} (m)", min_value=0, value=100, key=f"mission_alt_{i}"))
        mission_distances.append(dist)
        mission_altitudes.append(alt)
    if st.button("Estimate Mission Plan"):
        total_km = sum(mission_distances)
        avg_alt = sum(mission_altitudes) / len(mission_altitudes)
        st.write(f"Total planned distance: **{total_km:.2f} km**")
        st.write(f"Average flight altitude: **{avg_alt:.0f} m**")
        st.write("Leg breakdown:")
        for i, (d, a) in enumerate(zip(mission_distances, mission_altitudes)):
            st.write(f"• Leg {i+1}: {d:.2f} km at {a} m")

# === Optional JSON Report ===
if submitted:
    report = {
        "model": drone_model,
        "battery_wh": battery_capacity_wh,
        "payload_g": payload_weight_g,
        "flight_speed_kmh": flight_speed_kmh,
        "wind_kmh": wind_speed_kmh,
        "altitude_m": altitude_m,
        "elevation_gain": elevation_gain_m,
        "flight_mode": flight_mode,
        "cloud_cover_pct": cloud_cover,
        "gustiness": gustiness,
        "thermal_signature": delta_T,
        "estimated_minutes": flight_time_minutes,
        "power_draw_watt": total_draw,
        "battery_draw_only": battery_draw_only,
        "mission_legs": mission_legs,
        "mission_distances_km": mission_distances,
        "mission_altitudes_m": mission_altitudes,
        "timestamp": "{timestamp}"
    }
    report_str = json.dumps(report, indent=2)
    st.download_button("Download Simulation Report (JSON)", report_str, file_name="uav_sim_report.json")

    # Optional Thermal Chart
    st.subheader("Thermal Signature Over Time")
    sim_times = list(range(0, int(flight_time_minutes)+1))
    thermal_series = [delta_T + 2.5 * math.sin(0.6 * t) for t in sim_times]
    fig, ax = plt.subplots()
    ax.plot(sim_times, thermal_series)
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Thermal Signature ΔT (°C)")
    ax.set_title("Thermal Signature Over Time")
    st.pyplot(fig)
