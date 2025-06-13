
# UAV Battery Efficiency Estimator (Final Verified with Metadata Display)

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

def get_delta_color(delta_T):
    if delta_T < 10:
        return "green"
    elif delta_T < 20:
        return "orange"
    else:
        return "red"

def insert_thermal_and_fuel_outputs(total_draw, profile, flight_time_minutes, temperature_c, ir_shielding, delta_T):
    st.subheader("Thermal Signature & Fuel Analysis")
    risk = thermal_risk_rating(delta_T)
    color = get_delta_color(delta_T)
    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Thermal Signature Risk: {risk} (ΔT = {delta_T:.1f}°C)</span>", unsafe_allow_html=True)
    if profile["power_system"].lower() == "hybrid":
        burn_rate = 1.5 + (0.1 * gustiness) + ((terrain_penalty - 1) * 3)
        fuel_burned = calculate_fuel_consumption(
            power_draw_watt=total_draw,
            duration_hr=flight_time_minutes / 60,
            fuel_burn_rate_lph=burn_rate
        )
        st.metric(label="Estimated Fuel Used", value=f"{fuel_burned:.2f} L")
    else:
        st.info("Fuel tracking not applicable for battery-powered UAVs.")

# Define drone profiles
UAV_PROFILES = {
    "MQ-9 Reaper": {"max_payload_g": 1700000, "base_weight_kg": 2223, "power_system": "Hybrid", "draw_watt": 800, "battery_wh": 200, "crash_risk": True, "ai_capabilities": "Real-time threat detection, sensor fusion, autonomous target tracking"},
    "Custom Build": {"max_payload_g": 1500, "base_weight_kg": 2.0, "power_system": "Battery", "draw_watt": 180, "battery_wh": 150, "crash_risk": False, "ai_capabilities": "User-defined platform with configurable components"}
}

# Streamlit UI
st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')
st.markdown("<h1 style='color:#00FF00;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)
st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]
st.caption(f"Base weight: {profile['base_weight_kg']:.2f} kg — Max payload: {profile['max_payload_g']} g")
st.caption(f"Power system: `{profile['power_system']}`")
