
import streamlit as st
import time
import math

def calculate_hybrid_draw(total_draw_watts, power_system):
    if power_system.lower() == "hybrid":
        return total_draw_watts * 0.10
    return total_draw_watts

def calculate_fuel_consumption(power_draw_watt, duration_hr, fuel_burn_rate_lph=1.5):
    return fuel_burn_rate_lph * duration_hr if power_draw_watt > 0 else 0

def estimate_thermal_signature(draw_watt, efficiency, surface_area, emissivity, ambient_temp_C):
    sigma = 5.670374419e-8
    waste_heat = draw_watt * (1 - efficiency)
    if waste_heat <= 0 or surface_area <= 0 or emissivity <= 0:
        return 0
    temp_K = (waste_heat / (emissivity * sigma * surface_area)) ** 0.25
    temp_C = temp_K - 273.15
    delta_T = temp_C - ambient_temp_C
    return round(delta_T, 1)

def thermal_risk_rating(delta_T):
    if delta_T < 10:
        return "Low"
    elif delta_T < 20:
        return "Moderate"
    else:
        return "High"

def insert_thermal_and_fuel_outputs(total_draw, profile, flight_time_minutes, temperature_c, ir_shielding):
    st.subheader("Thermal Signature & Fuel Analysis")
    assumed_efficiency = 0.85
    assumed_surface_area = 0.3
    use_stealth_coating = False  # no need for dynamic checkbox
    emissivity = 0.3 if use_stealth_coating else 0.9

    delta_T = estimate_thermal_signature(
        draw_watt=total_draw,
        efficiency=assumed_efficiency,
        surface_area=assumed_surface_area,
        emissivity=emissivity,
        ambient_temp_C=temperature_c
    )
    delta_T *= ir_shielding
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

st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')
st.markdown("<h1 style='color:#00FF00;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)

UAV_PROFILES = {
    "Generic Quad": {"max_payload_g": 800, "base_weight_kg": 1.2, "power_system": "Battery", "draw_watt": 150, "battery_wh": 60, "crash_risk": False, "ai_capabilities": "Basic flight stabilization, waypoint navigation"},
    "DJI Phantom": {"max_payload_g": 500, "base_weight_kg": 1.4, "power_system": "Battery", "draw_watt": 120, "battery_wh": 68, "crash_risk": False, "ai_capabilities": "Visual object tracking, return-to-home, autonomous mapping"},
    "RQ-11 Raven": {"max_payload_g": 0, "base_weight_kg": 1.9, "power_system": "Battery", "draw_watt": 90, "battery_wh": 50, "crash_risk": False, "ai_capabilities": "Auto-stabilized flight, limited route autonomy"},
    "RQ-20 Puma": {"max_payload_g": 600, "base_weight_kg": 6.3, "power_system": "Battery", "draw_watt": 180, "battery_wh": 275, "crash_risk": False, "ai_capabilities": "AI-enhanced ISR mission planning, autonomous loitering"},
    "MQ-1 Predator": {"max_payload_g": 204000, "base_weight_kg": 512, "power_system": "Hybrid", "draw_watt": 650, "battery_wh": 150, "crash_risk": True, "ai_capabilities": "Semi-autonomous surveillance, pattern-of-life analysis"},
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "crash_risk": True, "ai_capabilities": "Real-time threat detection, sensor fusion, autonomous target tracking"},
    "Skydio 2+": {"max_payload_g": 150, "base_weight_kg": 0.8, "power_system": "Battery", "draw_watt": 90, "battery_wh": 45, "crash_risk": False, "ai_capabilities": "Full obstacle avoidance, visual SLAM, autonomous following"},
    "Freefly Alta 8": {"max_payload_g": 9000, "base_weight_kg": 6.2, "power_system": "Battery", "draw_watt": 400, "battery_wh": 710, "crash_risk": False, "ai_capabilities": "Autonomous camera coordination, precision loitering"},
    "Teal Golden Eagle": {"max_payload_g": 2000, "base_weight_kg": 2.2, "power_system": "Battery", "draw_watt": 220, "battery_wh": 100, "crash_risk": True, "ai_capabilities": "AI-driven ISR, edge-based visual classification, GPS-denied flight"},
    "Quantum Systems Vector": {"max_payload_g": 1500, "base_weight_kg": 2.3, "power_system": "Battery", "draw_watt": 160, "battery_wh": 150, "crash_risk": False, "ai_capabilities": "Modular AI sensor pods, onboard geospatial intelligence, autonomous route learning"},
    "Custom Build": {"max_payload_g": 1500, "base_weight_kg": 2.0, "power_system": "Battery", "draw_watt": 180, "battery_wh": 150, "crash_risk": False, "ai_capabilities": "User-defined platform with configurable components"}
}

debug_mode = st.checkbox("Enable Debug Mode")
drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

if "ai_capabilities" in profile:
    st.info(f"**AI Capabilities:** {profile['ai_capabilities']}")

if drone_model == "Custom Build":
    st.subheader("Custom Build Configuration")
    profile['draw_watt'] = st.number_input("Motor Power Draw (W)", min_value=10, value=180)
    profile['max_payload_g'] = st.number_input("Max Payload (g)", min_value=100, value=1500)
    profile['base_weight_kg'] = st.number_input("Base Weight (kg)", min_value=0.1, value=2.0)
    profile['battery_wh'] = st.number_input("Battery Capacity (Wh)", min_value=10, value=150)

max_lift = profile["max_payload_g"]
base_weight_kg = profile["base_weight_kg"]
default_battery = profile["battery_wh"]

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = st.number_input("Battery Capacity (Wh)", min_value=1.0, max_value=1850.0, value=float(default_battery))
    payload_weight_g = st.number_input("Payload Weight (g)", min_value=0, value=int(max_lift * 0.5))
    flight_speed_kmh = st.number_input("Flight Speed (km/h)", min_value=0.0, value=30.0)
    wind_speed_kmh = st.number_input("Wind Speed (km/h)", min_value=0.0, value=10.0)
    temperature_c = st.number_input("Temperature (°C)", value=25.0)
    altitude_m = st.number_input("Flight Altitude (m)", min_value=0, max_value=5000, value=0)
    elevation_gain_m = st.number_input("Elevation Gain (m)", min_value=-1000, max_value=1000, value=0)
    flight_mode = st.selectbox("Flight Mode", ["Hover", "Forward Flight", "Waypoint Mission"])
    simulate_failure = st.checkbox("Enable Failure Simulation (experimental)")

    st.subheader("Terrain Profile")
    terrain_type = st.selectbox("Terrain Type", ["Flat", "Hilly", "Mountainous"])
    terrain_penalty = {"Flat": 1.0, "Hilly": 1.05, "Mountainous": 1.15}[terrain_type]

    st.subheader("Stealth Loadout Presets")
    use_stealth_frame = st.checkbox("Low-RCS Frame Upgrade", value=False)
    use_ir_coating = st.checkbox("IR-Absorptive Paint", value=False)
    stealth_drag_penalty = 1.0 + (0.02 if use_stealth_frame else 0) + (0.01 if use_ir_coating else 0)

    st.subheader("Weather Conditions")
    cloud_cover = st.slider("Cloud Cover (%)", min_value=0, max_value=100, value=20)
    gustiness = st.slider("Wind Gust Factor (0 = calm, 10 = stormy)", min_value=0, max_value=10, value=3)

    submitted = st.form_submit_button("Estimate")
