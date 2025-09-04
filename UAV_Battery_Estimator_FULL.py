# Final_Full_App.py
# UAV Battery Efficiency Estimator — Aerospace-grade physics + LLM + Swarm + Stealth + Playback + CSV/JSON Export
# Full UAV profiles included. Individual UAV Detailed Results panel replaces the Quick Look table.
# Author: Tareq Omrani | 2025

import os, time, math, random, json, io
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple

import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd

# ─────────────────────────────────────────────────────────
# Optional LLM client (graceful fallback if no key present)
# ─────────────────────────────────────────────────────────
OPENAI_AVAILABLE = False
try:
    from openai import OpenAI
    _client = OpenAI()  # requires env var OPENAI_API_KEY
    OPENAI_AVAILABLE = True
except Exception:
    _client = None
    OPENAI_AVAILABLE = False

# ─────────────────────────────────────────────────────────
# Streamlit header / UX helpers
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title='UAV Battery Efficiency Estimator', layout='centered')

# Mobile-friendly: auto-select input text on focus for quick edits
st.markdown("""
    <script>
    const inputs = window.parent.document.querySelectorAll('input');
    inputs.forEach(el => el.addEventListener('focus', function(){ this.select(); }));
    </script>
""", unsafe_allow_html=True)

# Title (digital green)
st.markdown("<h1 style='color:#00FF00;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)
st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")

def numeric_input(label: str, default: float) -> float:
    """Mobile-friendly numeric input with default fallback and validation."""
    val_str = st.text_input(label, value=str(default))
    if val_str.strip() == "":
        return default
    try:
        return float(val_str)
    except ValueError:
        st.error(f"Please enter a valid number for {label}. Using default {default}.")
        return default
# ─────────────────────────────────────────────────────────
# Detectability model (AI/IR) helpers
# ─────────────────────────────────────────────────────────
def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def _risk_bucket(score: float):
    if score < 33:
        return ("Low", "success", "#0f9d58")
    elif score < 67:
        return ("Moderate", "warning", "#f4b400")
    else:
        return ("High", "error", "#db4437")

def _badge(label: str, score: float, bg: str) -> str:
    return (
        f"<span style='display:inline-block;padding:6px 10px;margin-right:8px;"
        f"border-radius:8px;background:{bg};color:#fff;font-weight:600;"
        f"font-size:13px;white-space:nowrap;'>{label}: {score:.0f}/100</span>"
    )

def compute_ai_ir_scores(delta_T: float, altitude_m: float, cloud_cover: int,
                         speed_kmh: float, gustiness: int, stealth_factor: float,
                         drone_type: str, power_system: str) -> Tuple[float, float]:
    # AI visual detectability
    alt_term = 1.0 - min(0.80, altitude_m / 800.0)
    speed_term = min(1.0, speed_kmh / 60.0) * 0.25
    type_bonus = 0.15 if drone_type == "rotor" else 0.07
    gust_term = min(0.15, (gustiness / 10.0) * 0.15)
    cloud_factor = 1.0 - 0.25 * (cloud_cover / 100.0)
    stealth_k = 1.0 - max(0.0, (stealth_factor - 1.0) * 0.15)
    ai_raw = (0.55 * alt_term) + (0.15 * type_bonus) + (0.10 * speed_term) + (0.05 * gust_term)
    ai_score = 100.0 * _clamp01(ai_raw * cloud_factor * stealth_k)

    # IR thermal detectability
    delta_norm = _clamp01(delta_T / 22.0)
    alt_atten = 1.0 - min(0.60, (altitude_m / 1200.0) * 0.60)
    cloud_attn = 1.0 - 0.30 * (cloud_cover / 100.0)
    ice_bias = 0.10 if power_system == "ICE" else 0.00
    stealth_k2 = 1.0 - max(0.0, (stealth_factor - 1.0) * 0.10)
    ir_raw = (0.70 * delta_norm) + ice_bias
    ir_score = 100.0 * _clamp01(ir_raw * alt_atten * cloud_attn * stealth_k2)

    return ai_score, ir_score

def render_detectability_alert(ai_score: float, ir_score: float) -> Tuple[str, str]:
    ai_label, _, ai_bg = _risk_bucket(ai_score)
    ir_label, _, ir_bg = _risk_bucket(ir_score)
    overall_kind = "error" if "High" in (ai_label, ir_label) else ("warning" if "Moderate" in (ai_label, ir_label) else "success")
    badges = (
        "<div style='margin:6px 0;'>"
        f"{_badge(f'AI Visual • {ai_label}', ai_score, ai_bg)}"
        f"{_badge(f'IR Thermal • {ir_label}', ir_score, ir_bg)}"
        "</div>"
    )
    return overall_kind, badges

# ─────────────────────────────────────────────────────────
# Physics helpers (aerospace-grade) + Universal Fix Strategy
# ─────────────────────────────────────────────────────────
RHO0 = 1.225       # kg/m^3 sea-level
P0   = 101325.0    # Pa
T0K  = 288.15      # K
LAPSE= 0.0065      # K/m
R_AIR= 287.05
G0   = 9.80665
SIGMA= 5.670374419e-8  # W/m^2K^4

# Global realism constants
USABLE_BATT_FRAC  = 0.85
USABLE_FUEL_FRAC  = 0.90
DISPATCH_RESERVE  = 0.30  # 30% reserve on time/energy
HOTEL_W_DEFAULT   = 15.0  # avionics/radio/CPU baseline
INSTALL_FRAC_DEF  = 0.15  # installation/trim losses on aero polar
DEFAULT_MIN_AIRSPEED_MS = 8.0  # ~30 km/h fallback

# ─────────────────────────────────────────────────────────
# Universal guard-rails and helper functions
# ─────────────────────────────────────────────────────────
def clamp_min_speed(drone_model: str, V_ms_cmd: float, SPEC_BOOK: dict = {}) -> float:
    """Clamp commanded speed to platform minimum (stall/loiter floor)."""
    V_min_ms = SPEC_BOOK.get(drone_model, {}).get("min_airspeed_ms", DEFAULT_MIN_AIRSPEED_MS)
    if V_ms_cmd < V_min_ms:
        st.warning(f"Speed {V_ms_cmd*3.6:.0f} km/h < platform minimum; clamped to {V_min_ms*3.6:.0f} km/h.")
    return max(V_ms_cmd, V_min_ms)

def heading_range_km(V_air_ms: float, W_ms: float, t_min: float) -> Tuple[float,float]:
    """Return (best_km, worst_km). Worst=0 if upwind infeasible (W ≥ V_air). Units fixed to km."""
    t_h = max(0.0, t_min) / 60.0
    if V_air_ms <= 0.1:
        return (0.0, 0.0)
    if W_ms >= V_air_ms:
        return ((V_air_ms + W_ms) * t_h * 3.6, 0.0)
    worst = (V_air_ms - W_ms) * t_h * 3.6
    best  = (V_air_ms + W_ms) * t_h * 3.6
    return (best, worst)

def estimate_skin_area(profile: dict) -> float:
    """Estimate radiating skin area from published geometry."""
    if "wing_area_m2" in profile:
        wing_area = profile["wing_area_m2"]
        if profile.get("power_system") == "ICE":
            return wing_area * 5.0   # slender MALE fuselage + tail + nacelle factors
        else:
            return wing_area * 4.0   # small battery fixed-wing
    elif "rotor_WL_proxy" in profile:
        return 0.8                   # rotorcraft proxy area
    else:
        return 1.0                   # safe fallback

def air_density(alt_m: float, sea_level_temp_C: float = 15.0) -> float:
    """ISA troposphere density (up to ~11 km)."""
    T0 = sea_level_temp_C + 273.15
    if alt_m < 0: alt_m = 0.0
    T  = max(1.0, T0 - LAPSE * alt_m)
    p  = P0 * (1.0 - (LAPSE*alt_m)/T0) ** (G0/(R_AIR*LAPSE))
    return p/(R_AIR*T)

def density_ratio(alt_m: float, sea_level_temp_C: float = 15.0) -> Tuple[float, float]:
    rho = air_density(alt_m, sea_level_temp_C)
    return rho, rho / RHO0

def rotorcraft_density_scale(rho_ratio: float) -> float:
    """Ideal induced-power scaling for rotors: P_induced ∝ 1/sqrt(ρ)."""
    return 1.0 / max(0.3, math.sqrt(max(1e-4, rho_ratio)))

def drag_polar_cd(cd0: float, cl: float, e: float, aspect_ratio: float) -> float:
    k = 1.0 / (math.pi * max(0.3, e) * max(2.0, aspect_ratio))
    return cd0 + k * (cl ** 2)

def aero_power_required_W(weight_N: float, rho: float, V_ms: float,
                          wing_area_m2: float, cd0: float, e: float,
                          wingspan_m: float, prop_eff: float) -> float:
    """Shaft power required using drag polar + dynamic pressure."""
    V_ms = max(1.0, V_ms)
    q = 0.5 * rho * V_ms * V_ms
    cl = weight_N / (q * max(1e-6, wing_area_m2))
    AR = (wingspan_m ** 2) / max(1e-6, wing_area_m2)
    cd = drag_polar_cd(cd0, cl, e, AR)
    D = q * wing_area_m2 * cd
    return (D * V_ms) / max(0.3, prop_eff)

def realistic_fixedwing_power(weight_N, rho, V_ms,
                              wing_area_m2, wingspan_m,
                              cd0, e, prop_eff,
                              hotel_W=HOTEL_W_DEFAULT, install_frac=INSTALL_FRAC_DEF,
                              payload_drag_delta=0.0) -> float:
    """
    Bounded aero + hotel + installation/trim losses for fixed-wing battery draw.
    These bounds keep small-UAV polars in a realistic regime.
    """
    CD0   = max(0.05, cd0 + max(0.0, payload_drag_delta))
    E_OSW = min(0.70, e)
    ETA_P = min(0.65, max(0.55, prop_eff))
    P_polar = aero_power_required_W(weight_N, rho, V_ms, wing_area_m2, CD0, E_OSW, wingspan_m, ETA_P)
    return hotel_W + (1.0 + install_frac) * P_polar

def gust_penalty_fraction(gustiness_index: int,
                          wind_kmh: float,
                          V_ms: float,
                          wing_loading_Nm2: float) -> float:
    """
    Nonlinear gust penalty. Heavier penalty for low wing-loading and strong gusts.
    Returns fractional increase in power draw (0.0 .. 0.35).
    """
    gust_ms = max(0.0, 0.6 * float(gustiness_index))  # 0..6 m/s from slider 0..10
    V_ms = max(3.0, V_ms)
    WL = max(25.0, wing_loading_Nm2)
    WL_ref = 70.0  # typical small fixed-wing WL
    base = 1.5 * (gust_ms / V_ms) ** 2 * (WL_ref / WL) ** 0.7
    wind_ms = max(0.0, wind_kmh / 3.6)
    bias = 0.03 * (wind_ms / 8.0)
    frac = max(0.0, min(0.35, base + bias))
    return frac

# ─────────────────────────────────────────────────────────
# Geometry-scaled convective/radiative thermal model
# ─────────────────────────────────────────────────────────
THERMAL_CAP_C = 80.0        # conservative realism cap (°C above ambient)
DEFAULT_EMISSIVITY = 0.85

def convective_radiative_deltaT_geom(Q_shaft_W: float,
                                     hotel_W: float,
                                     surface_area_m2: float,
                                     emissivity: float,
                                     ambient_C: float,
                                     rho: float,
                                     V_ms: float,
                                     power_fraction_to_skin: float) -> float:
    """
    Geometry-aware ΔT model:
    - Only a fraction of shaft power heats the skin (power_fraction_to_skin, ~0.06–0.10).
    - A portion of hotel load also becomes skin heat (assume 60% → structure).
    - Convection scales with √V and ρ via a conservative mixed correlation.
    - Radiation linearized near ambient: 4 ε σ T^3.
    """
    if surface_area_m2 <= 0.0 or emissivity <= 0.0:
        return 0.0
    V_ms = max(0.5, V_ms)

    # Effective waste heat that reaches skin
    Q_skin = max(0.0, Q_shaft_W * max(0.0, power_fraction_to_skin) + hotel_W * 0.60)

    # Convection (mixed correlation; conservative floor)
    h_nat = 6.0
    h_forced = 10.45 - V_ms + 10.0 * math.sqrt(V_ms)
    h = max(h_nat, h_forced) * (rho / RHO0)  # scale by density ratio

    # Radiation near ambient
    T_ambK = ambient_C + 273.15
    rad_coeff = 4.0 * emissivity * SIGMA * (T_ambK ** 3)  # W/m²K

    sink_W_per_K = (h + rad_coeff) * surface_area_m2
    if sink_W_per_K <= 0.0:
        return 0.0

    dT = Q_skin / sink_W_per_K
    return max(0.2, min(THERMAL_CAP_C, dT))

# ─────────────────────────────────────────────────────────
# Energy & fuel helpers
# ─────────────────────────────────────────────────────────
def climb_energy_wh(total_mass_kg: float, climb_m: float) -> float:
    """Battery: m g h converted to Wh (1 Wh = 3600 J)."""
    if climb_m <= 0:
        return 0.0
    return (total_mass_kg * 9.81 * climb_m) / 3600.0

def bsfc_fuel_burn_lph(power_W: float, bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    """ICE: fuel burn (L/h) from shaft power and BSFC."""
    fuel_kg_per_h = (bsfc_gpkwh / 1000.0) * (power_W / 1000.0)  # g/kWh → kg/h
    return fuel_kg_per_h / max(0.5, fuel_density_kgpl)

def climb_fuel_liters(total_mass_kg: float, climb_m: float,
                      bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    """
    ICE: convert m g h to required fuel via BSFC (kWh).
    Conservative: assumes engine runs near the same SFC during climb energy.
    """
    if climb_m <= 0:
        return 0.0
    E_kWh = (total_mass_kg * 9.81 * climb_m) / 3_600_000.0
    fuel_kg = (bsfc_gpkwh / 1000.0) * E_kWh
    return fuel_kg / max(0.5, fuel_density_kgpl)
# ─────────────────────────────────────────────────────────
# UAV profiles (FULL SET)
# ─────────────────────────────────────────────────────────
UAV_PROFILES: Dict[str, Dict[str, Any]] = {
    # ——— Small multirotors / COTS ———
    "Generic Quad": {
        "type": "rotor",
        "max_payload_g": 800, "base_weight_kg": 1.2,
        "power_system": "Battery", "draw_watt": 150, "battery_wh": 60,
        "rotor_WL_proxy": 45.0,
        "ai_capabilities": "Basic flight stabilization, waypoint navigation",
        "crash_risk": False
    },
    "DJI Phantom": {
        "type": "rotor",
        "max_payload_g": 500, "base_weight_kg": 1.4,
        "power_system": "Battery", "draw_watt": 120, "battery_wh": 68,
        "rotor_WL_proxy": 50.0,
        "ai_capabilities": "Visual object tracking, return-to-home, autonomous mapping",
        "crash_risk": False
    },
    "Skydio 2+": {
        "type": "rotor",
        "max_payload_g": 150, "base_weight_kg": 0.8,
        "power_system": "Battery", "draw_watt": 90, "battery_wh": 45,
        "rotor_WL_proxy": 40.0,
        "ai_capabilities": "Full obstacle avoidance, visual SLAM, autonomous following",
        "crash_risk": False
    },
    "Freefly Alta 8": {
        "type": "rotor",
        "max_payload_g": 9000, "base_weight_kg": 6.2,
        "power_system": "Battery", "draw_watt": 400, "battery_wh": 710,
        "rotor_WL_proxy": 60.0,
        "ai_capabilities": "Autonomous camera coordination, precision loitering",
        "crash_risk": False
    },

    # ——— Small tactical / fixed-wing ———
    "RQ-11 Raven": {
        "type": "fixed",
        "max_payload_g": 0, "base_weight_kg": 1.9,
        "power_system": "Battery", "draw_watt": 90, "battery_wh": 400,
        "wing_area_m2": 0.24, "wingspan_m": 1.4,
        "cd0": 0.035, "oswald_e": 0.75, "prop_eff": 0.72,
        "ai_capabilities": "Auto-stabilized flight, limited route autonomy",
        "crash_risk": False
    },
    "RQ-20 Puma": {
        "type": "fixed",
        "max_payload_g": 600, "base_weight_kg": 6.3,
        "power_system": "Battery", "draw_watt": 180, "battery_wh": 600,
        "wing_area_m2": 0.55, "wingspan_m": 2.8,
        "cd0": 0.040, "oswald_e": 0.75, "prop_eff": 0.72,
        "ai_capabilities": "AI-enhanced ISR mission planning, autonomous loitering",
        "crash_risk": False
    },
    "Teal Golden Eagle": {
        "type": "fixed",
        "max_payload_g": 2000, "base_weight_kg": 2.2,
        "power_system": "Battery", "draw_watt": 220, "battery_wh": 100,
        "wing_area_m2": 0.30, "wingspan_m": 2.1,
        "cd0": 0.045, "oswald_e": 0.74, "prop_eff": 0.70,
        "ai_capabilities": "AI-driven ISR, edge-based visual classification, GPS-denied flight",
        "crash_risk": True
    },
    "Quantum Systems Vector": {
        "type": "fixed",
        "max_payload_g": 1500, "base_weight_kg": 2.3,
        "power_system": "Battery", "draw_watt": 160, "battery_wh": 150,
        "wing_area_m2": 0.55, "wingspan_m": 2.8,
        "cd0": 0.038, "oswald_e": 0.80, "prop_eff": 0.78,
        "ai_capabilities": "Modular AI sensor pods, onboard geospatial intelligence, autonomous route learning",
        "crash_risk": False
    },

    # ——— MALE class (ICE) ———
    "MQ-1 Predator": {
        "type": "fixed",
        "max_payload_g": 204000, "base_weight_kg": 512,
        "power_system": "ICE", "draw_watt": 650, "battery_wh": 150,
        "wing_area_m2": 11.5, "wingspan_m": 14.8,
        "cd0": 0.025, "oswald_e": 0.80, "prop_eff": 0.80,
        "bsfc_gpkwh": 260.0, "fuel_density_kgpl": 0.72, "fuel_tank_l": 300.0,
        "ai_capabilities": "Semi-autonomous surveillance, pattern-of-life analysis",
        "crash_risk": True
    },
    "MQ-9 Reaper": {
        "type": "fixed",
        "max_payload_g": 1700000, "base_weight_kg": 2223,
        "power_system": "ICE", "draw_watt": 800, "battery_wh": 200,
        "wing_area_m2": 24.0, "wingspan_m": 20.0,
        "cd0": 0.030, "oswald_e": 0.85, "prop_eff": 0.82,
        "bsfc_gpkwh": 330.0, "fuel_density_kgpl": 0.80, "fuel_tank_l": 900.0,
        "ai_capabilities": "Real-time threat detection, sensor fusion, autonomous target tracking",
        "crash_risk": True
    },

    # ——— Sandbox / Custom ———
    "Custom Build": {
        "type": "rotor",
        "max_payload_g": 1500, "base_weight_kg": 2.0,
        "power_system": "Battery", "draw_watt": 180, "battery_wh": 150,
        "rotor_WL_proxy": 50.0,
        "ai_capabilities": "User-defined platform with configurable components",
        "crash_risk": False
    }
}

# ─────────────────────────────────────────────────────────
# SPEC BOOK — conservative envelopes for sanity checks
# (These are non-blocking guard-rails used to annotate results.)
# ─────────────────────────────────────────────────────────
SPEC_BOOK: Dict[str, Dict[str, Any]] = {
    # Multirotors (indicative)
    "Generic Quad": {
        "min_airspeed_ms": 0.0,
        "endurance_range_hr": (0.15, 0.50),   # 9–30 min
        "cruise_kmh_range": (0, 55)
    },
    "DJI Phantom": {
        "min_airspeed_ms": 0.0,
        "endurance_range_hr": (0.18, 0.45),   # 11–27 min
        "cruise_kmh_range": (0, 60)
    },
    "Skydio 2+": {
        "min_airspeed_ms": 0.0,
        "endurance_range_hr": (0.15, 0.45),   # ~9–27 min
        "cruise_kmh_range": (0, 60)
    },
    "Freefly Alta 8": {
        "min_airspeed_ms": 0.0,
        "endurance_range_hr": (0.15, 0.40),   # ~9–24 min (payload dependent)
        "cruise_kmh_range": (0, 55)
    },

    # Small tactical fixed-wing (indicative)
    "RQ-11 Raven": {
        "min_airspeed_ms": 10.0,              # ~36 km/h loiter-ish
        "endurance_range_hr": (1.0, 1.5),     # ~60–90 min
        "cruise_kmh_range": (50, 80)
    },
    "RQ-20 Puma": {
        "min_airspeed_ms": 12.0,              # ~43 km/h
        "endurance_range_hr": (1.5, 3.5),     # ~90–210 min
        "cruise_kmh_range": (45, 75)
    },
    "Teal Golden Eagle": {
        "min_airspeed_ms": 12.0,
        "endurance_range_hr": (0.7, 1.8),
        "cruise_kmh_range": (40, 90)
    },
    "Quantum Systems Vector": {
        "min_airspeed_ms": 12.0,
        "endurance_range_hr": (1.5, 2.5),
        "cruise_kmh_range": (50, 90)
    },

    # MALE (conservative envelopes)
    "MQ-1 Predator": {
        "min_airspeed_ms": 28.0,              # ~100 km/h conservative min
        "endurance_range_hr": (18, 28),       # ~18–28 h
        "cruise_kmh_range": (120, 220)
    },
    "MQ-9 Reaper": {
        "min_airspeed_ms": 33.0,              # ~120 km/h conservative min
        "endurance_range_hr": (20, 30),       # ~20–30 h
        "cruise_kmh_range": (200, 300)
    },

    # Custom
    "Custom Build": {
        "min_airspeed_ms": 8.0,
        "endurance_range_hr": (0.3, 2.0),
        "cruise_kmh_range": (30, 120)
    },
}

def spec_for(model: str) -> Dict[str, Any]:
    """Lookup spec envelope for a given model name."""
    return SPEC_BOOK.get(model, {})

def envelope_msg(val: float, lo: float, hi: float, unit: str) -> Optional[str]:
    """Return human message if value falls outside a conservative envelope."""
    if val < lo:
        return f"Below conservative envelope (min {lo:g} {unit})."
    if val > hi:
        return f"Above conservative envelope (max {hi:g} {unit})."
    return None
# ─────────────────────────────────────────────────────────
# Stealth loadout presets (drag + IR scaling)
# ─────────────────────────────────────────────────────────
STEALTH_LOADOUTS = {
    "Clean": {"drag": 1.0, "ir_factor": 1.0},
    "Low Observable": {"drag": 1.15, "ir_factor": 0.85},
    "Heavy Stealth": {"drag": 1.25, "ir_factor": 0.70}
}

# ─────────────────────────────────────────────────────────
# Debug toggles & model selection
# ─────────────────────────────────────────────────────────
debug_mode = st.checkbox("Enable Debug Mode")
allow_pack_override = st.checkbox("Allow Battery Override (debug)", value=False) if debug_mode else False

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

st.info(f"**AI Capabilities:** {profile.get('ai_capabilities','—')}")
st.caption(f"Base weight: {profile['base_weight_kg']} kg — Max payload: {profile['max_payload_g']} g")
st.caption(f"Power system: `{profile['power_system']}` | Type: `{profile['type']}`")

# Dynamic flight modes
if profile["type"] == "fixed":
    flight_mode_options = ["Forward Flight", "Loiter", "Waypoint Mission"]
else:
    flight_mode_options = ["Hover", "Forward Flight", "Loiter", "Waypoint Mission"]

# ─────────────────────────────────────────────────────────
# Main form
# ─────────────────────────────────────────────────────────
with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = numeric_input("Battery Capacity (Wh)", float(profile.get("battery_wh", 100.0)))
    payload_weight_g    = int(numeric_input("Payload (g)", min(max(0, int(profile["max_payload_g"]*0.5)), profile["max_payload_g"])))
    flight_speed_kmh    = numeric_input("Speed (km/h)", 30.0)
    wind_speed_kmh      = numeric_input("Wind (km/h)", 10.0)
    temperature_c       = numeric_input("Temperature (°C)", 25.0)
    altitude_m          = int(numeric_input("Altitude (m)", 0))
    elevation_gain_m    = int(numeric_input("Elevation Gain (m)", 0))
    flight_mode         = st.selectbox("Flight Mode", flight_mode_options)
    cloud_cover         = st.slider("Cloud Cover (%)", 0, 100, 50)
    gustiness           = st.slider("Gust Factor", 0, 10, 2)
    terrain_penalty     = st.slider("Terrain Complexity", 1.0, 1.5, 1.1)

    # Stealth loadout dropdown (replaces manual slider)
    stealth_choice = st.selectbox("Stealth Loadout", list(STEALTH_LOADOUTS.keys()))
    stealth_drag_penalty = STEALTH_LOADOUTS[stealth_choice]["drag"]
    stealth_ir_factor    = STEALTH_LOADOUTS[stealth_choice]["ir_factor"]

    simulate_failure    = st.checkbox("Enable Failure Simulation")

    ice_params = None
    if profile["power_system"] == "ICE":
        st.markdown("### Aerospace Model (ICE-only)")
        fuel_tank_l       = numeric_input("Fuel Tank (L)", float(profile.get("fuel_tank_l", 300.0)))
        cd0               = numeric_input("C_D0 (parasite)", float(profile.get("cd0", 0.025)))
        wing_area_m2      = numeric_input("Wing Area S (m²)", float(profile.get("wing_area_m2", 11.5)))
        wingspan_m        = numeric_input("Wingspan b (m)", float(profile.get("wingspan_m", 14.8)))
        oswald_e          = numeric_input("Oswald e", float(profile.get("oswald_e", 0.80)))
        prop_eff          = numeric_input("Propulsive η_p", float(profile.get("prop_eff", 0.80)))
        bsfc_gpkwh        = numeric_input("BSFC (g/kWh)", float(profile.get("bsfc_gpkwh", 260.0)))
        fuel_density_kgpl = numeric_input("Fuel Density (kg/L)", float(profile.get("fuel_density_kgpl", 0.72)))
        hybrid_assist     = st.checkbox("Enable Hybrid Assist (experimental)")
        assist_fraction   = st.slider("Assist Fraction", 0.05, 0.30, 0.10, step=0.01)
        assist_duration_min = st.slider("Assist Duration (minutes)", 1, 30, 10)

        ice_params = dict(
            fuel_tank_l=fuel_tank_l, wing_area_m2=wing_area_m2, wingspan_m=wingspan_m,
            cd0=cd0, oswald_e=oswald_e, prop_eff=prop_eff,
            bsfc_gpkwh=bsfc_gpkwh, fuel_density_kgpl=fuel_density_kgpl,
            hybrid_assist=hybrid_assist, assist_fraction=assist_fraction,
            assist_duration_min=assist_duration_min
        )

    submitted = st.form_submit_button("Estimate")
# ─────────────────────────────────────────────────────────
# Simulation + Results
# ─────────────────────────────────────────────────────────
if submitted:
    try:
        if payload_weight_g > profile["max_payload_g"]:
            st.error("Payload exceeds lift capacity."); st.stop()

        # Clamp battery unless override
        if profile["power_system"] == "Battery":
            battery_capacity_wh = max(
                0.0,
                battery_capacity_wh if allow_pack_override else min(battery_capacity_wh, profile["battery_wh"])
            )

        total_weight_kg = profile["base_weight_kg"] + (payload_weight_g / 1000.0)
        start_batt_wh_for_gauge = battery_capacity_wh
        V_ms_cmd = max(0.1, (flight_speed_kmh / 3.6))
        V_ms = clamp_min_speed(drone_model, V_ms_cmd, SPEC_BOOK)
        rho, rho_ratio = density_ratio(altitude_m, temperature_c)
        weight_N = total_weight_kg * 9.81
        W_ms = max(0.0, wind_speed_kmh / 3.6)
        use_ice_branch = profile["power_system"] == "ICE" and (ice_params is not None)

        # Temperature derate for cells
        if profile["power_system"] == "Battery":
            if temperature_c < 15:
                battery_capacity_wh *= 0.90
            elif temperature_c > 35:
                battery_capacity_wh *= 0.95
            start_batt_wh_for_gauge = battery_capacity_wh

        # Atmosphere & key factors
        st.header("Atmospheric Conditions")
        st.metric("Air Density ρ", f"{rho:.3f} kg/m³")
        st.metric("Density Ratio ρ/ρ₀", f"{rho_ratio:.3f}")

        st.header("Applied Environment Factors")
        if profile["type"] == "rotor":
            density_factor = rotorcraft_density_scale(rho_ratio)
            st.markdown(
                f"**Air density factor:** `{rho_ratio:.3f}` (ρ/ρ₀)  —  "
                f"**Rotor power factor:** `{density_factor:.3f}` (∝ 1/√ρ)"
            )
        else:
            st.markdown(f"**Air density factor:** `{rho_ratio:.3f}` (ρ/ρ₀) — handled via lift/drag in aero model.")

        # Shared for detailed panel
        detail: Dict[str, Any] = {
            "drone_model": drone_model,
            "type": profile["type"],
            "power_system": profile["power_system"],
            "payload_g": payload_weight_g,
            "total_mass_kg": round(total_weight_kg, 3),
            "V_ms_cmd": round(V_ms_cmd, 3),
            "V_ms": round(V_ms, 3),
            "W_ms": round(W_ms, 3),
            "rho": round(rho, 4),
            "rho_ratio": round(rho_ratio, 4),
            "cloud_cover_%": cloud_cover,
            "gustiness": gustiness,
            "terrain_factor": terrain_penalty,
            "stealth_drag_factor": stealth_drag_penalty,
            "altitude_m": altitude_m,
            "temperature_C": temperature_c,
            "flight_mode": flight_mode
        }

        # ————————————————————————————————
        # ICE aerospace branch (MALE UAVs)
        # ————————————————————————————————
        if use_ice_branch:
            # Clamp unconstrained aero inputs
            CD0   = max(0.05, ice_params["cd0"])
            E_OSW = min(0.70, ice_params["oswald_e"])
            ETA_P = min(0.65, max(0.55, ice_params["prop_eff"]))

            # Effective loiter speed
            V_ms_eff = V_ms if flight_mode != "Loiter" else max(8.0, 0.6 * V_ms)

            # Shaft power from aero polar
            P_req_W = aero_power_required_W(
                weight_N=weight_N, rho=rho, V_ms=V_ms_eff,
                wing_area_m2=ice_params["wing_area_m2"],
                cd0=CD0, e=E_OSW,
                wingspan_m=ice_params["wingspan_m"], prop_eff=ETA_P
            )

            # Mission penalties
            if flight_mode == "Waypoint Mission":
                P_req_W *= 1.05
            elif flight_mode == "Loiter":
                P_req_W *= 1.10

            # Gust penalty
            WL = weight_N / max(0.05, ice_params["wing_area_m2"])
            wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms_eff, WL)
            P_req_W *= (1.0 + wind_penalty_frac)

            # Terrain & stealth
            P_req_W *= terrain_penalty * stealth_drag_penalty

            # Add hotel load
            P_total_W = P_req_W + HOTEL_W_DEFAULT

            # Fuel burn
            lph = bsfc_fuel_burn_lph(P_total_W, ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"])

            # Climb fuel
            climb_L_val = climb_fuel_liters(total_weight_kg, max(0, elevation_gain_m),
                                            ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"])

            # Usable fuel
            usable_fuel_L_start = max(0.0, ice_params["fuel_tank_l"] * USABLE_FUEL_FRAC - max(0.0, climb_L_val))
            usable_fuel_L = usable_fuel_L_start

            # Hybrid assist
            if ice_params["hybrid_assist"]:
                battery_support_Wh = float(profile.get("battery_wh", 200.0))
                assist_power_W = max(0.0, P_total_W * ice_params["assist_fraction"])
                assist_energy_Wh = assist_power_W * (ice_params["assist_duration_min"] / 60.0)
                if assist_energy_Wh > battery_support_Wh:
                    ice_params["assist_duration_min"] = (battery_support_Wh / max(1.0, assist_power_W)) * 60.0
                    assist_energy_Wh = battery_support_Wh
                saved_L_per_hr = bsfc_fuel_burn_lph(assist_power_W, ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"])
                fuel_saved_L = saved_L_per_hr * (ice_params["assist_duration_min"] / 60.0)
                usable_fuel_L += fuel_saved_L

            # Endurance & ranges
            raw_endurance_hr = usable_fuel_L / max(0.05, lph)
            raw_endurance_min = raw_endurance_hr * 60.0
            dispatch_endurance_min = raw_endurance_min * (1.0 - DISPATCH_RESERVE)

            best_km, worst_km = heading_range_km(V_ms_eff, W_ms, dispatch_endurance_min)

            # Thermal model
            surf_area_m2 = estimate_skin_area(profile)
            power_frac_skin = 0.08
            delta_T = convective_radiative_deltaT_geom(
                Q_shaft_W=P_req_W, hotel_W=HOTEL_W_DEFAULT, surface_area_m2=surf_area_m2,
                emissivity=DEFAULT_EMISSIVITY, ambient_C=temperature_c,
                rho=rho, V_ms=V_ms_eff, power_fraction_to_skin=power_frac_skin
            )
            delta_T *= (1.0 - 0.20 * (cloud_cover / 100.0))

            # Detectability
            ai_score, ir_score = compute_ai_ir_scores(
                delta_T=delta_T * stealth_ir_factor,
                altitude_m=altitude_m, cloud_cover=cloud_cover,
                speed_kmh=flight_speed_kmh, gustiness=gustiness,
                stealth_factor=stealth_drag_penalty, drone_type=profile["type"],
                power_system=profile["power_system"]
            )
            overall_kind, badges_html = render_detectability_alert(ai_score, ir_score)
        # ————————————————————————————————
        # Battery/Hybrid branch (rotor + fixed)
        # ————————————————————————————————
        else:
            if profile["type"] == "rotor":
                # Rotorcraft: base draw scaled by mass & density + parasitic ~V^2
                base_draw = float(profile.get("draw_watt", 180.0))
                weight_factor = total_weight_kg / max(0.1, profile["base_weight_kg"])
                density_factor = rotorcraft_density_scale(rho_ratio)  # √(ρ0/ρ)
                V_term = 0.018 * (flight_speed_kmh ** 2)
                total_draw = (base_draw * weight_factor * density_factor) + V_term
                # Gust penalty (rotor WL proxy)
                WL_proxy = float(profile.get("rotor_WL_proxy", 45.0))
                wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms, WL_proxy)
                total_draw *= (1.0 + wind_penalty_frac)

                # Mission penalties
                if flight_mode == "Waypoint Mission":
                    total_draw *= 1.05
                elif flight_mode == "Loiter":
                    total_draw *= 1.08  # steady circling
                elif flight_mode == "Hover":
                    total_draw *= 1.10  # station-keeping

                V_ref_ms = V_ms
                ref_surface = estimate_skin_area(profile)
                detail.update({
                    "rotor_base_draw_W": base_draw,
                    "weight_factor": round(weight_factor,3),
                    "density_factor_rotor": round(density_factor,3),
                    "V_parasitic_term_W": round(V_term,2),
                    "WL_proxy": WL_proxy
                })

            else:
                # Fixed-wing battery: bounded aero + hotel + install losses
                wing_area_m2 = float(profile.get("wing_area_m2", 0.5))
                wingspan_m   = float(profile.get("wingspan_m", 2.0))
                cd0          = float(profile.get("cd0", 0.05))
                e            = float(profile.get("oswald_e", 0.70))
                prop_eff     = float(profile.get("prop_eff", 0.60))

                # Loiter as low-speed endurance setting
                V_ms_eff = V_ms if flight_mode != "Loiter" else max(8.0, 0.6 * V_ms)

                total_draw = realistic_fixedwing_power(
                    weight_N=weight_N, rho=rho, V_ms=V_ms_eff,
                    wing_area_m2=wing_area_m2, wingspan_m=wingspan_m,
                    cd0=cd0, e=e, prop_eff=prop_eff,
                    hotel_W=HOTEL_W_DEFAULT, install_frac=INSTALL_FRAC_DEF,
                    payload_drag_delta=(0.002 if payload_weight_g > 0 else 0.0)
                )
                # Gust penalty via wing loading
                WL = weight_N / max(0.05, wing_area_m2)
                wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms_eff, WL)
                total_draw *= (1.0 + wind_penalty_frac)
                # Mission penalties
                if flight_mode == "Waypoint Mission":
                    total_draw *= 1.05
                elif flight_mode == "Loiter":
                    total_draw *= 1.10

                V_ref_ms = V_ms_eff
                ref_surface = estimate_skin_area(profile)
                detail.update({
                    "wing_area_m2": wing_area_m2, "wingspan_m": wingspan_m,
                    "cd0_eff": max(0.05, cd0 + (0.002 if payload_weight_g>0 else 0.0)),
                    "e_oswald_eff": min(0.70, e),
                    "eta_prop_eff": min(0.65, max(0.55, prop_eff)),
                    "V_ms_effective": round(V_ms_eff,3),
                    "wing_loading_N_per_m2": round(WL,2)
                })

            # Terrain & stealth
            total_draw *= terrain_penalty * stealth_drag_penalty

            # Climb/Descent energy for battery
            climb_energy_Wh_value = 0.0
            if elevation_gain_m > 0:
                climb_energy_Wh_value = climb_energy_wh(total_weight_kg, elevation_gain_m)
                battery_capacity_wh -= climb_energy_Wh_value
            elif elevation_gain_m < 0:
                recov = (total_weight_kg * 9.81 * abs(elevation_gain_m) / 3600.0) * 0.20
                battery_capacity_wh += recov
                detail["descent_recovery_Wh"] = round(recov, 2)

            # Usable energy + reserve
            batt_temp_derated_Wh = battery_capacity_wh
            usable_Wh = max(0.0, batt_temp_derated_Wh) * USABLE_BATT_FRAC
            t_raw_min = (usable_Wh / max(5.0, total_draw)) * 60.0
            dispatch_endurance_min = t_raw_min * (1.0 - DISPATCH_RESERVE)

            # Vector wind ranges (based on V_ref_ms)
            best_km, worst_km = heading_range_km(V_ref_ms, W_ms, dispatch_endurance_min)

            # Thermal (geometry-scaled; fraction of electrical → skin)
            Q_shaft_proxy = max(0.0, total_draw - HOTEL_W_DEFAULT)  # proxy for aero/prop share
            delta_T = convective_radiative_deltaT_geom(
                Q_shaft_W=Q_shaft_proxy, hotel_W=HOTEL_W_DEFAULT, surface_area_m2=ref_surface,
                emissivity=DEFAULT_EMISSIVITY, ambient_C=temperature_c,
                rho=rho, V_ms=V_ref_ms, power_fraction_to_skin=0.08
            )
            delta_T *= (1.0 - 0.20 * (cloud_cover / 100.0))

            # Detectability
            ai_score, ir_score = compute_ai_ir_scores(
                delta_T=delta_T, altitude_m=altitude_m, cloud_cover=cloud_cover,
                speed_kmh=flight_speed_kmh, gustiness=gustiness,
                stealth_factor=stealth_drag_penalty, drone_type=profile["type"],
                power_system=profile["power_system"]
            )
            overall_kind, badges_html = render_detectability_alert(ai_score, ir_score)

            # Detail panel (Battery)
            detail.update({
                "total_draw_W": round(total_draw,1),
                "wind_penalty_frac": round(wind_penalty_frac,4),
                "terrain_x_stealth_factor": round(terrain_penalty*stealth_drag_penalty,3),
                "climb_energy_Wh": round(climb_energy_Wh_value,2),
                "battery_derated_Wh": round(batt_temp_derated_Wh,2),
                "usable_battery_Wh": round(usable_Wh,2),
                "raw_endurance_min": round(t_raw_min,2),
                "skin_area_m2": round(ref_surface,3),
                "thermal_deltaT_C": round(delta_T,1)
            })

            wind_penalty_pct = wind_penalty_frac * 100.0
            flight_time_minutes = dispatch_endurance_min
            climb_L = None

            # Total distance (km)
            total_distance_km = (flight_time_minutes / 60.0) * float(flight_speed_kmh)

            # User-facing metrics (Battery)
            st.subheader("Thermal Signature & Battery")
            risk = 'Low' if delta_T < 10 else ('Moderate' if delta_T < 20 else 'High')
            st.metric("Thermal Signature Risk", f"{risk} (ΔT = {delta_T:.1f}°C)")
            st.metric("Total Draw (incl. hotel/penalties)", f"{total_draw:.0f} W")

        # ————————————————————————————————
        # Detectability alert (both branches)
        # ————————————————————————————————
        st.subheader("AI/IR Detectability Alert")
        if overall_kind == "success":
            st.success("Overall detectability: LOW")
        elif overall_kind == "warning":
            st.warning("Overall detectability: MODERATE")
        else:
            st.error("Overall detectability: HIGH")
        st.markdown(badges_html, unsafe_allow_html=True)

        # ————————————————————————————————
        # Mission performance metrics
        # ————————————————————————————————
        lo = flight_time_minutes * 0.90
        hi = flight_time_minutes * 1.10

        st.header("Selected UAV — Mission Performance")
        st.metric("Dispatchable Endurance", f"{flight_time_minutes:.1f} minutes")
        st.caption(f"Uncertainty band: {lo:.1f}–{hi:.1f} min (±10%)")
        st.metric("Total Distance (km)", f"{total_distance_km:.1f} km")
        st.metric("Best Heading Range", f"{best_km:.1f} km")
        st.metric("Upwind Range", f"{worst_km:.1f} km")

        # Human summary
        st.header("Individual UAV Detailed Results (Selected Model)")
        human = []
        human.append(f"- **Model**: {drone_model} ({profile['type']}, {profile['power_system']})")
        human.append(f"- **Payload used**: {payload_weight_g} g (max {profile['max_payload_g']} g)")
        human.append(f"- **Mass**: {total_weight_kg:.3f} kg")
        human.append(f"- **Atmosphere**: ρ={rho:.3f} kg/m³, ρ/ρ0={rho_ratio:.3f}, T={temperature_c:.1f}°C, Alt={altitude_m} m")
        human.append(f"- **Speed (cmd→clamped)**: {V_ms_cmd*3.6:.1f} → {V_ms*3.6:.1f} km/h, Wind={wind_speed_kmh:.1f} km/h")
        if use_ice_branch:
            human.append(f"- **Power (shaft+hotel)**: {detail.get('P_total_W',0)/1000:.2f} kW")
            human.append(f"- **Fuel burn**: {detail.get('fuel_burn_L_per_hr',0):.2f} L/h")
            human.append(f"- **Usable fuel (after climb/assist)**: {detail.get('usable_fuel_L_after_assist',0):.2f} L")
            if ice_params and ice_params.get("hybrid_assist", False):
                human.append(f"- **Hybrid Assist**: {ice_params['assist_fraction']*100:.0f}% for {ice_params['assist_duration_min']:.0f} min")
        else:
            human.append(f"- **Total draw (incl. hotel/penalties)**: {detail.get('total_draw_W',0):.1f} W")
            if elevation_gain_m != 0:
                human.append(f"- **Climb/Descent net energy**: {detail.get('climb_energy_Wh',0):.2f} Wh (desc recov: {detail.get('descent_recovery_Wh','0.00')} Wh)")
        human.append(f"- **Gust penalty**: {wind_penalty_pct:.1f}%")
        human.append(f"- **Thermal ΔT (geometry-scaled)**: {delta_T:.1f} °C")
        human.append(f"- **Dispatchable Endurance**: {flight_time_minutes:.1f} min")
        human.append(f"- **Total Distance (km)**: {total_distance_km:.2f} km")
        human.append(f"- **Best heading / Upwind ranges**: {best_km:.2f} km / {worst_km:.2f} km")
        human.append(f"- **Detectability (AI visual / IR thermal)**: {ai_score:.0f}/100 / {ir_score:.0f}/100")
        human.append(f"- **Overall Detectability**: {'LOW' if overall_kind=='success' else 'MODERATE' if overall_kind=='warning' else 'HIGH'}")
        st.markdown("\n".join(human))

        # Machine-readable JSON for the detailed panel
        detail.update({
            "dispatch_endurance_min": round(flight_time_minutes,1),
            "total_distance_km": round(total_distance_km,2),
            "best_heading_range_km": round(best_km,2),
            "upwind_range_km": round(worst_km,2),
            "thermal_deltaT_C": round(delta_T,1),
            "wind_penalty_%": round(wind_penalty_pct,1),
            "ai_visual_score_0_100": round(ai_score,1),
            "ir_thermal_score_0_100": round(ir_score,1),
            "detectability_overall": ("LOW" if overall_kind=="success" else "MODERATE" if overall_kind=="warning" else "HIGH")
        })
        st.json(detail, expanded=False)

        # ————————————————————————————————
        # Universal Sanity Checks (non-blocking)
        # ————————————————————————————————
        st.subheader("Sanity Checks (non-blocking)")
        checks = []
        spec = spec_for(drone_model)

        # Endurance vs envelope (convert to hours)
        end_hr = max(0.0, flight_time_minutes / 60.0)
        if "endurance_range_hr" in spec:
            loE, hiE = spec["endurance_range_hr"]
            msg = envelope_msg(end_hr, loE, hiE, "hr")
            if msg:
                checks.append(("Endurance", f"{end_hr:.2f} hr — {msg}"))

        # Cruise/loiter speed vs envelope (use actual ground-speed input)
        if "cruise_kmh_range" in spec:
            loV, hiV = spec["cruise_kmh_range"]
            msg = envelope_msg(float(flight_speed_kmh), loV, hiV, "km/h")
            if msg:
                checks.append(("Speed", f"{flight_speed_kmh:.0f} km/h — {msg}"))

        # Thermal realism guard
        if delta_T >= THERMAL_CAP_C * 0.95:
            checks.append(("Thermal", f"ΔT={delta_T:.1f}°C near cap ({THERMAL_CAP_C}°C). Geometry or power fraction may be conservative."))

        # ICE plausibility of fuel burn (broad bounds)
        if use_ice_branch:
            if not (0.5 <= lph <= 120.0):
                checks.append(("Fuel Burn", f"{lph:.2f} L/h outside broad plausibility band (0.5–120). Check weights/drag/BSFC."))

        if not checks:
            st.success("All results fall within conservative envelopes.")
        else:
            for title, msg in checks:
                st.warning(f"**{title}:** {msg}")

        # ————————————————————————————————
        # Exports
        # ————————————————————————————————
        indiv_df = pd.DataFrame([detail])
        st.download_button(
            "⬇️ Download Individual UAV Detailed Results (CSV)",
            data=indiv_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{drone_model.replace(' ','_').lower()}_detailed_results.csv",
            mime="text/csv"
        )
        st.download_button(
            "⬇️ Download Individual UAV Detailed Results (JSON)",
            data=json.dumps(detail, indent=2),
            file_name=f"{drone_model.replace(' ','_').lower()}_detailed_results.json",
            mime="application/json"
        )

        results = {
            "Drone Model": drone_model,
            "Power System": profile["power_system"],
            "Type": profile["type"],
            "Flight Mode": flight_mode,
            "Battery Capacity (Wh)": round(battery_capacity_wh, 2) if profile["power_system"]=="Battery" else profile.get("battery_wh", 0),
            "Payload (g)": int(payload_weight_g),
            "Speed (km/h)": float(flight_speed_kmh),
            "Wind (km/h)": float(wind_speed_kmh),
            "Gustiness (0-10)": int(gustiness),
            "Altitude (m)": int(altitude_m),
            "Air Density (kg/m³)": round(rho, 3),
            "Density Ratio (ρ/ρ0)": round(rho_ratio, 3),
            "Wind Penalty (%)": round(wind_penalty_pct, 1),
            "Climb Energy (Wh)": None if use_ice_branch else round(detail.get("climb_energy_Wh", 0.0), 2),
            "Climb Fuel (L)": round(climb_L, 2) if climb_L is not None else None,
            "Dispatchable Endurance (min)": round(flight_time_minutes, 1),
            "Total Distance (km)": round(total_distance_km, 2),
            "Best Heading Range (km)": round(best_km, 2),
            "Upwind Range (km)": round(worst_km, 2),
            "ΔT (°C)": round(delta_T, 1),
            "AI Visual Detectability (0-100)": round(ai_score,1),
            "IR Thermal Detectability (0-100)": round(ir_score,1),
            "Overall Detectability": ("LOW" if overall_kind=="success" else "MODERATE" if overall_kind=="warning" else "HIGH")
        }

        df_res = pd.DataFrame([results])
        csv_buffer = io.BytesIO()
        df_res.to_csv(csv_buffer, index=False)
        st.download_button(
            "⬇️ Download Scenario Summary (CSV)",
            data=csv_buffer,
            file_name="mission_results.csv",
            mime="text/csv"
        )

        json_str = json.dumps(results, indent=2)
        st.download_button(
            "⬇️ Download Scenario Summary (JSON)",
            data=json_str,
            file_name="mission_results.json",
            mime="application/json"
        )
        st.text_area("Scenario Summary (JSON Copy-Paste)", json_str, height=250)
        # ————————————————————————————————
        # AI Mission Advisor (LLM)
        # ————————————————————————————————
        if 'generate_llm_advice' not in globals():
            def generate_llm_advice(params: Dict[str, Any]) -> str:
                if not OPENAI_AVAILABLE:
                    return ("LLM unavailable — heuristic advice:\n"
                            "- Fly near best-endurance speed.\n"
                            "- Descend 100–200 m if gusts rise.\n"
                            "- Consider assist / lighten payload.\n"
                            "- Use cloud cover tactically.")
                prompt = f"""
You are an aerospace UAV mission planner. Provide 3–5 short recommendations.

Parameters:
- Drone: {params['drone']}
- Payload: {params['payload_g']} g
- Mode: {params['mode']}
- Speed: {params['speed_kmh']} km/h
- Altitude: {params['alt_m']} m
- Wind: {params['wind_kmh']} km/h (gust {params['gust']})
- Dispatchable Endurance: {params['endurance_min']:.1f} min
- Thermal ΔT: {params['delta_T']:.1f} °C
- Fuel context: {params['fuel_l']}
- Hybrid assist: {params.get('hybrid_assist', False)} (fraction={params.get('assist_fraction',0):.2f}, duration={params.get('assist_duration_min',0)} min)

Be concise, bullet style.
"""
                try:
                    resp = _client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role":"system","content":"You are a precise UAV mission advisor."},
                                  {"role":"user","content":prompt}],
                        temperature=0.35, max_tokens=260
                    )
                    return resp.choices[0].message.content.strip()
                except Exception:
                    return ("LLM error — heuristic advice:\n"
                            "- Fly near best-endurance speed.\n"
                            "- Descend to denser air if temps allow.\n"
                            "- Use assist only in high-threat sectors.")
        st.subheader("AI Mission Advisor (LLM)")
        _advisor_params = {
            "drone": drone_model,
            "payload_g": payload_weight_g,
            "mode": flight_mode,
            "speed_kmh": flight_speed_kmh,
            "alt_m": altitude_m,
            "wind_kmh": wind_speed_kmh,
            "gust": gustiness,
            "endurance_min": float(flight_time_minutes),
            "delta_T": float(delta_T),
            "fuel_l": (detail.get("usable_fuel_L_after_assist", 0.0) if profile["power_system"] == "ICE" else 0.0),
            "hybrid_assist": (profile["power_system"] == "ICE" and bool(ice_params and ice_params.get("hybrid_assist", False))),
            "assist_fraction": (float(ice_params.get("assist_fraction", 0.0)) if ice_params else 0.0),
            "assist_duration_min": (float(ice_params.get("assist_duration_min", 0.0)) if ice_params else 0.0),
        }
        st.write(generate_llm_advice(_advisor_params))

        # ————————————————————————————————
        # Swarm & Stealth — UI controls (rendered here if missing earlier)
        # ————————————————————————————————
        st.markdown("### Swarm & Stealth")
        swarm_enable = st.checkbox("Enable Swarm Advisor", value=True, key="swarm_enable_ui")
        swarm_size = st.slider("Swarm Size", 2, 8, 3, key="swarm_size_ui")
        swarm_steps = st.slider("Swarm Conversation Rounds", 1, 5, 2, key="swarm_steps_ui")
        stealth_ingress = st.checkbox("Enable Stealth Ingress Mode", value=True, key="stealth_ingress_ui")
        threat_zone_km = st.slider("Threat Zone Radius (km)", 1.0, 20.0, 5.0, key="threat_zone_ui")

        with st.expander("Mission Waypoints"):
            st.caption("Enter waypoints as (x,y) km coordinates relative to origin.")
            waypoint_str = st.text_area("Waypoints (e.g., 2,2; 5,0; 8,-3)", "2,2; 5,0; 8,-3", key="wp_text_ui")

        _waypoints = []
        try:
            for _pair in waypoint_str.split(";"):
                _x_str, _y_str = _pair.split(",")
                _waypoints.append((float(_x_str.strip()), float(_y_str.strip())))
        except Exception:
            st.error("Invalid waypoint format. Using (0,0).")
            _waypoints = [(0.0, 0.0)]

        # ————————————————————————————————
        # Swarm agent scaffolding (guards to avoid re-def)
        # ————————————————————————————————
        if 'ALLOWED_ACTIONS' not in globals():
            ALLOWED_ACTIONS = ["RTB","LOITER","HANDOFF_TRACK","RELOCATE","ALTITUDE_CHANGE","SPEED_CHANGE","RELAY_COMMS","STANDBY","HYBRID_ASSIST"]

        if 'AgentState' not in globals():
            @dataclass
            class AgentState:
                id: str
                role: str
                platform: str
                endurance_min: float
                battery_wh: float
                fuel_l: float
                speed_kmh: float
                altitude_m: int
                x_km: float
                y_km: float
                delta_T: float
                hybrid_assist: bool = False
                assist_fraction: float = 0.0
                assist_time_min: float = 0.0
                waypoints: Optional[list] = None
                current_wp: int = 0
                warning: str = ""

        if 'summarize_state' not in globals():
            def summarize_state(s: AgentState) -> Dict[str, Any]:
                d = asdict(s).copy()
                d.pop("waypoints", None)
                return d

        if 'seed_swarm' not in globals():
            def seed_swarm(n, base_endurance, base_batt_wh, delta_T_ref, altitude_m_ref, platform) -> List[AgentState]:
                roles = ["LEAD","SCOUT","TRACKER","RELAY","STRIKER"]
                out=[]
                for i in range(n):
                    role=roles[i%len(roles)]
                    out.append(AgentState(
                        id=f"UAV_{i+1}", role=role, platform=platform,
                        endurance_min=float(random.uniform(0.7,1.1)*max(5.0, base_endurance)),
                        battery_wh=float(random.uniform(0.8,1.1)*max(10.0, base_batt_wh)),
                        fuel_l=float(random.uniform(70.0,200.0) if "MQ-" in platform else random.uniform(5.0,25.0)),
                        speed_kmh=float(random.uniform(25,40)), altitude_m=int(altitude_m_ref+random.uniform(-20,20)),
                        x_km=float(random.uniform(-1,1)), y_km=float(random.uniform(-1,1)),
                        delta_T=float(delta_T_ref*random.uniform(0.9,1.2))
                    ))
                return out

        if '_safe_json' not in globals():
            def _safe_json(txt: str) -> Dict[str, Any]:
                try:
                    return json.loads(txt)
                except Exception:
                    s,e=txt.find("{"), txt.rfind("}")
                    return json.loads(txt[s:e+1])

        if 'AGENT_SYSTEM_TMPL' not in globals():
            AGENT_SYSTEM_TMPL = """You are {role} for {uav_id}, a UAV swarm agent.
Return STRICT JSON:
- "message": short comms (<20 words)
- "proposed_action": one of {allowed}
- "params": dict (assist: {{"fraction":0-0.3,"duration_min":1-20}})
- "confidence": 0-1 float
Rules:
- If endurance < 8 → prefer RTB/hand-off.
- If threat_note='elevated' and platform is MQ-1/MQ-9 → consider HYBRID_ASSIST.
"""

        if 'LEAD_SYSTEM' not in globals():
            LEAD_SYSTEM = """You are LEAD, the swarm orchestrator.
Input: env + UAV states + proposals.
Output STRICT JSON with:
- "conversation": [{ "from":"...", "msg":"..." }]
- "actions": [{ "uav_id":"...", "action":"...", "reason":"...", ...params }]
Rules:
- HYBRID_ASSIST only for MQ-1/MQ-9.
- If stealth_ingress=true AND UAV inside threat_zone_km, prefer HYBRID_ASSIST (not all at once).
- If low endurance, RTB over assist.
"""

        if 'agent_call' not in globals():
            def agent_call(env: Dict[str,Any], s: AgentState) -> Dict[str, Any]:
                if not OPENAI_AVAILABLE:
                    if env.get("threat_note")=="elevated" and ("MQ-1" in s.platform or "MQ-9" in s.platform):
                        return {"message":"Stealth assist on","proposed_action":"HYBRID_ASSIST","params":{"fraction":0.15,"duration_min":10},"confidence":0.7}
                    return {"message":"Loitering","proposed_action":"LOITER","params":{},"confidence":0.6}
                sys = AGENT_SYSTEM_TMPL.format(role=s.role, uav_id=s.id, allowed=ALLOWED_ACTIONS)
                payload = {"env": env, "self": summarize_state(s)}
                try:
                    resp = _client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role":"system","content":sys},
                                  {"role":"user","content": json.dumps(payload, ensure_ascii=False)}],
                        temperature=0.2, max_tokens=220, response_format={"type":"json_object"}
                    )
                    return _safe_json(resp.choices[0].message.content)
                except Exception:
                    return {"message":"Standby","proposed_action":"STANDBY","params":{},"confidence":0.5}

        if 'lead_call' not in globals():
            def lead_call(env: Dict[str,Any], swarm: List[AgentState], proposals: Dict[str,Any]) -> Dict[str, Any]:
                if not OPENAI_AVAILABLE:
                    actions=[]
                    for s in swarm:
                        prop = proposals.get(s.id,{})
                        act = prop.get("proposed_action","LOITER")
                        if act=="HYBRID_ASSIST" and ("MQ-1" in s.platform or "MQ-9" in s.platform):
                            actions.append({"uav_id":s.id,"action":"HYBRID_ASSIST","fraction":0.15,"duration_min":10,"reason":"Stealth ingress"})
                        elif s.endurance_min<8:
                            actions.append({"uav_id":s.id,"action":"RTB","reason":"Low endurance"})
                        else:
                            actions.append({"uav_id":s.id,"action":"LOITER","reason":"Holding"})
                    return {"conversation":[{"from":"LEAD","msg":"Fallback fusion active"}],"actions":actions}
                packed = {"env": env,"swarm":[summarize_state(s) for s in swarm],"proposals": proposals,"allowed_actions": ALLOWED_ACTIONS}
                try:
                    resp = _client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role":"system","content":LEAD_SYSTEM},
                                  {"role":"user","content": json.dumps(packed, ensure_ascii=False)}],
                        temperature=0.2, max_tokens=600, response_format={"type":"json_object"}
                    )
                    return _safe_json(resp.choices[0].message.content)
                except Exception:
                    return {"conversation":[{"from":"LEAD","msg":"LLM error fallback"}],
                            "actions":[{"uav_id":s.id,"action":"LOITER","reason":"LLM error"} for s in swarm]}

        if 'apply_actions' not in globals():
            def apply_actions(swarm: List[AgentState], acts: List[Dict[str,Any]],
                              stealth_ingress: bool, threat_zone_km: float) -> List[AgentState]:
                def in_zone(s: AgentState) -> bool:
                    return (s.x_km**2 + s.y_km**2)**0.5 <= threat_zone_km
                idx = {s.id: s for s in swarm}
                for a in acts:
                    s = idx.get(a.get("uav_id"))
                    if not s: continue
                    act = a.get("action")
                    if act == "HYBRID_ASSIST" and ("MQ-1" in s.platform or "MQ-9" in s.platform):
                        frac = float(a.get("fraction",0.10)); dur = float(a.get("duration_min",8))
                        s.hybrid_assist=True; s.assist_fraction=frac; s.assist_time_min=dur
                        s.delta_T *= (1 - frac*0.7); s.fuel_l += 0.05*dur
                        s.warning = f"Hybrid Assist {frac*100:.0f}% for {dur:.0f} min"
                    elif act == "RTB":
                        s.warning="RTB ordered"; s.speed_kmh=max(15,s.speed_kmh)
                    elif act == "LOITER":
                        s.speed_kmh = max(10, s.speed_kmh*0.9)
                    elif act == "RELOCATE":
                        s.x_km += float(a.get("dx_km",0)); s.y_km += float(a.get("dy_km",0))
                    elif act == "ALTITUDE_CHANGE":
                        s.altitude_m += int(a.get("delta_m",0))
                    elif act == "SPEED_CHANGE":
                        s.speed_kmh += float(a.get("delta_kmh",0))
                    elif act == "RELAY_COMMS":
                        s.warning="Relay"
                    s.endurance_min = max(0, s.endurance_min - random.uniform(0.5, 1.5))
                if stealth_ingress:
                    for s in swarm:
                        if ("MQ-1" in s.platform or "MQ-9" in s.platform) and in_zone(s) and not s.hybrid_assist:
                            s.hybrid_assist=True; s.assist_fraction=0.15; s.assist_time_min=10
                            s.delta_T *= (1 - 0.15*0.7); s.fuel_l += 0.5
                            s.warning="Auto Hybrid Assist (Stealth Ingress)"
                return swarm

        if 'plot_swarm_map' not in globals():
            def plot_swarm_map(swarm: List[AgentState], threat_zone_km: float,
                               stealth_ingress: bool, waypoints=None):
                fig, ax = plt.subplots(figsize=(5, 5))
                if stealth_ingress:
                    circle = plt.Circle((0, 0), threat_zone_km, color='red', alpha=0.2, label="Threat Zone")
                    ax.add_patch(circle)
                if waypoints:
                    xs, ys = zip(*waypoints)
                    ax.plot(xs, ys, "k--", linewidth=1, label="Mission Path")
                    ax.scatter(xs, ys, c="orange", marker="x", s=80, label="Waypoints")
                for s in swarm:
                    color = "blue"; marker = "o"
                    if s.platform in ["MQ-1 Predator","MQ-9 Reaper"]: marker="s"; color="purple"
                    if s.hybrid_assist: color="green"
                    ax.scatter(s.x_km, s.y_km, c=color, marker=marker, s=100, label=s.id)
                    ax.text(s.x_km+0.2, s.y_km+0.2, f"{s.id}\nAlt {s.altitude_m}m\nΔT {s.delta_T:.1f}°C", fontsize=7)
                ax.set_title("Swarm Mission Map")
                ax.set_xlabel("X (km)"); ax.set_ylabel("Y (km)")
                ax.axhline(0, color='grey', linewidth=0.5); ax.axvline(0, color='grey', linewidth=0.5)
                handles, labels = ax.get_legend_handles_labels(); uniq = dict(zip(labels, handles))
                ax.legend(uniq.values(), uniq.keys(), loc="upper right", fontsize=6)
                ax.set_aspect('equal', adjustable='datalim')
                return fig

        # ————————————————————————————————
        # Swarm Advisor workflow
        # ————————————————————————————————
        if swarm_enable:
            st.header("Swarm Advisor (Multi-Agent LLM)")
            base_endurance = float(max(5.0, flight_time_minutes))
            base_batt_wh = float(max(10.0, (battery_capacity_wh if profile["power_system"]=="Battery" else 200.0)))
            swarm = seed_swarm(swarm_size, base_endurance, base_batt_wh, delta_T, altitude_m, platform=drone_model)
            for s in swarm:
                s.waypoints = _waypoints.copy()
                s.current_wp = 0

            st.write("**Initial Swarm State**")
            for s in swarm:
                st.write(f"- {s.id} [{s.role}] ({s.platform}) — End {s.endurance_min:.1f} min | "
                         f"Fuel {s.fuel_l:.1f} L | Alt {s.altitude_m} m | Pos ({s.x_km:+.1f},{s.y_km:+.1f}) km | ΔT {s.delta_T:.1f}°C")

            env = {
                "wind_kmh": wind_speed_kmh,
                "gust": gustiness,
                "mission": flight_mode,
                "threat_note": ("elevated" if (simulate_failure or delta_T > 15 or altitude_m > 100) else "normal"),
                "stealth_ingress": stealth_ingress,
                "threat_zone_km": threat_zone_km
            }

            for round_idx in range(swarm_steps):
                st.subheader(f"Round {round_idx+1}")
                proposals = {s.id: agent_call(env, s) for s in swarm}
                fused = lead_call(env, swarm, proposals)
                if fused.get("conversation"):
                    st.markdown("**Swarm Conversation**")
                    for m in fused["conversation"]:
                        st.write(f"**{m.get('from','LEAD')}:** {m.get('msg','')}")
                acts = fused.get("actions", [])
                if acts:
                    st.markdown("**LEAD Actions**")
                    for a in acts:
                        tag = (f" (fraction={a.get('fraction',0):.2f}, duration={a.get('duration_min',0)} min)"
                               if a.get("action")=="HYBRID_ASSIST" else "")
                        st.write(f"- {a.get('uav_id')} → `{a.get('action')}` — {a.get('reason','')}{tag}")
                    swarm = apply_actions(swarm, acts, stealth_ingress, threat_zone_km)
                else:
                    st.info("No actions returned.")
                st.markdown("**Updated Swarm State**")
                for s in swarm:
                    assist_txt = f" [Assist {s.assist_fraction*100:.0f}% {s.assist_time_min:.0f} min]" if s.hybrid_assist else ""
                    zone_flag = "🟥 IN ZONE" if (stealth_ingress and ((s.x_km**2 + s.y_km**2)**0.5 <= threat_zone_km)) else ""
                    alert = f" ⚠ {s.warning}" if s.warning else ""
                    st.write(f"- {s.id} [{s.role}] — End {s.endurance_min:.1f} min | Fuel {s.fuel_l:.1f} L | Alt {s.altitude_m} m | ΔT {s.delta_T:.1f}°C{assist_txt}{alert} {zone_flag}")

            # Playback history + simple waypoint following
            st.subheader("Mission Playback")
            swarm_history = []
            timesteps = 10

            def move_towards(s: AgentState, target: tuple, step_km: float = 0.5):
                tx, ty = target
                dx, dy = tx - s.x_km, ty - s.y_km
                dist = (dx**2 + dy**2)**0.5
                if dist < step_km:
                    s.x_km, s.y_km = tx, ty
                    s.current_wp = min(s.current_wp + 1, (len(s.waypoints)-1 if s.waypoints else 0))
                elif dist > 0:
                    s.x_km += step_km * dx/dist
                    s.y_km += step_km * dy/dist
                return s

            for t in range(timesteps):
                snapshot = []
                for s in swarm:
                    if s.waypoints and s.current_wp < len(s.waypoints):
                        s = move_towards(s, s.waypoints[s.current_wp])
                    s.endurance_min = max(0, s.endurance_min - random.uniform(0.5, 1.0))
                    # crude burn-down for fuel to provide visual dynamics
                    s.fuel_l = max(0, s.fuel_l - (random.uniform(0.6, 1.6) if "MQ-" in s.platform else random.uniform(0.1, 0.5)))
                    if stealth_ingress and s.platform in ["MQ-1 Predator","MQ-9 Reaper"] and ((s.x_km**2 + s.y_km**2)**0.5 <= threat_zone_km):
                        s.hybrid_assist = True; s.assist_fraction = 0.15; s.assist_time_min = 10
                        s.delta_T *= (1 - 0.15*0.7); s.warning = "Auto Hybrid Assist (Stealth Ingress)"
                    snapshot.append(asdict(s))
                swarm_history.append(snapshot)

            frame = st.slider("Mission Time (minutes)", 0, timesteps-1, 0, key="playback_slider")
            frame_swarm = [AgentState(**data) for data in swarm_history[frame]]

            for s in frame_swarm:
                assist_txt = f" [Assist {s.assist_fraction*100:.0f}% {s.assist_time_min:.0f} min]" if s.hybrid_assist else ""
                zone_flag = "🟥 IN ZONE" if (stealth_ingress and ((s.x_km**2 + s.y_km**2)**0.5 <= threat_zone_km)) else ""
                alert = f" ⚠ {s.warning}" if s.warning else ""
                st.write(f"- {s.id} [{s.role}] — End {s.endurance_min:.1f} min | Fuel {s.fuel_l:.1f} L | Alt {s.altitude_m} m | ΔT {s.delta_T:.1f}°C{assist_txt}{alert} {zone_flag}")

            fig = plot_swarm_map(frame_swarm, threat_zone_km, stealth_ingress, _waypoints)
            st.pyplot(fig)
            plt.close(fig)

            # CSV exports
            rows=[]
            for t, snapshot in enumerate(swarm_history):
                for s in snapshot:
                    rows.append({
                        "time_min": t, "uav_id": s["id"], "role": s["role"], "platform": s["platform"],
                        "x_km": s["x_km"], "y_km": s["y_km"], "altitude_m": s["altitude_m"],
                        "endurance_min": s["endurance_min"], "fuel_l": s["fuel_l"], "delta_T": s["delta_T"],
                        "hybrid_assist": s["hybrid_assist"], "assist_fraction": s["assist_fraction"],
                        "assist_time_min": s["assist_time_min"], "warning": s["warning"]
                    })
            df = pd.DataFrame(rows)
            st.subheader("Export Mission Data")
            st.download_button(
                "Download Swarm Playback CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="swarm_mission_playback.csv",
                mime="text/csv"
            )

        # Wrap up caption
        st.caption("Swarm & Stealth restored — LLM advisor, stealth ingress, playback map, and CSV export now active.")
        # ————————————————————————————————
        # Heuristic suggestions
        # ————————————————————————————————
        st.subheader("AI Suggestions (Heuristics)")
        if payload_weight_g == profile["max_payload_g"]:
            st.write("**Tip:** Payload is at maximum lift capacity.")
        if wind_speed_kmh > 15:
            st.write("**Tip:** High wind may reduce flight time and upwind range.")
        if profile["power_system"] == "Battery" and battery_capacity_wh < 30:
            st.write("**Tip:** Battery is under 30 Wh. Consider a larger pack.")
        if flight_mode in ["Hover", "Waypoint Mission", "Loiter"]:
            st.write("**Tip:** Maneuvering or station-keeping increases power draw; plan extra reserve.")
        if stealth_drag_penalty > 1.2:
            st.write("**Tip:** Stealth loadout may reduce endurance.")
        if delta_T > 15:
            st.write("**Tip:** Thermal load is high. Consider lighter payload or lower altitude.")
        if altitude_m > 100:
            st.write("**Tip:** Flying above 100 m may increase detection risk.")

        st.caption("GPT-UAV Planner | Aerospace realism update — geometry-scaled thermal, range units fix, universal sanity checks, and Swarm & Stealth restored.")

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)

                          
