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
# ─────────────────────────────────────────────────────────
SPEC_BOOK: Dict[str, Dict[str, Any]] = {
    "Generic Quad": {"min_airspeed_ms": 0.0, "endurance_range_hr": (0.15, 0.50), "cruise_kmh_range": (0, 55)},
    "DJI Phantom": {"min_airspeed_ms": 0.0, "endurance_range_hr": (0.18, 0.45), "cruise_kmh_range": (0, 60)},
    "Skydio 2+": {"min_airspeed_ms": 0.0, "endurance_range_hr": (0.15, 0.45), "cruise_kmh_range": (0, 60)},
    "Freefly Alta 8": {"min_airspeed_ms": 0.0, "endurance_range_hr": (0.15, 0.40), "cruise_kmh_range": (0, 55)},
    "RQ-11 Raven": {"min_airspeed_ms": 10.0, "endurance_range_hr": (1.0, 1.5), "cruise_kmh_range": (50, 80)},
    "RQ-20 Puma": {"min_airspeed_ms": 12.0, "endurance_range_hr": (1.5, 3.5), "cruise_kmh_range": (45, 75)},
    "Teal Golden Eagle": {"min_airspeed_ms": 12.0, "endurance_range_hr": (0.7, 1.8), "cruise_kmh_range": (40, 90)},
    "Quantum Systems Vector": {"min_airspeed_ms": 12.0, "endurance_range_hr": (1.5, 2.5), "cruise_kmh_range": (50, 90)},
    "MQ-1 Predator": {"min_airspeed_ms": 28.0, "endurance_range_hr": (18, 28), "cruise_kmh_range": (120, 220)},
    "MQ-9 Reaper": {"min_airspeed_ms": 33.0, "endurance_range_hr": (20, 30), "cruise_kmh_range": (200, 300)},
    "Custom Build": {"min_airspeed_ms": 8.0, "endurance_range_hr": (0.3, 2.0), "cruise_kmh_range": (30, 120)},
}
# ─────────────────────────────────────────────────────────
# Physics helpers (aerospace-grade) + Universal Fix Strategy
# ─────────────────────────────────────────────────────────
RHO0 = 1.225       # kg/m^3 sea-level
P0   = 101325.0    # Pa
T0K  = 288.15      # K
LAPSE= 0.0065      # K/m
R_AIR= 287.05
G0   = 9.80665
SIGMA= 5.670374419e-8  # Stefan–Boltzmann W/m^2K^4

# Global realism constants
USABLE_BATT_FRAC  = 0.85
USABLE_FUEL_FRAC  = 0.90
DISPATCH_RESERVE  = 0.30  # 30% reserve on time/energy
HOTEL_W_DEFAULT   = 15.0  # avionics/radio/CPU baseline
INSTALL_FRAC_DEF  = 0.15  # installation/trim losses on aero polar
DEFAULT_MIN_AIRSPEED_MS = 8.0  # ~30 km/h fallback
THERMAL_CAP_C = 80.0  # conservative realism cap (°C above ambient)
DEFAULT_EMISSIVITY = 0.85

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
# Universal guard-rails and helper functions
# ─────────────────────────────────────────────────────────
def clamp_min_speed(drone_model: str, V_ms_cmd: float, SPEC_BOOK: dict = {}) -> float:
    """Clamp commanded speed to platform minimum (stall/loiter floor)."""
    V_min_ms = SPEC_BOOK.get(drone_model, {}).get("min_airspeed_ms", DEFAULT_MIN_AIRSPEED_MS)
    if V_ms_cmd < V_min_ms:
        st.warning(f"Speed {V_ms_cmd*3.6:.0f} km/h < platform minimum; clamped to {V_min_ms*3.6:.0f} km/h.")
    return max(V_ms_cmd, V_min_ms)

def heading_range_km(V_air_ms: float, W_ms: float, t_min: float) -> Tuple[float,float]:
    """Return (best_km, worst_km). Worst=0 if upwind infeasible (W ≥ V_air)."""
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
        if profile.get("power_system") == "ICE":   # MQ-1, MQ-9 etc.
            return wing_area * 5.0
        else:  # battery fixed-wing
            return wing_area * 4.0
    elif "rotor_WL_proxy" in profile:
        return 0.8  # rotorcraft proxy
    else:
        return 1.0

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
    """Bounded aero + hotel + installation/trim losses for fixed-wing battery draw."""
    CD0   = max(0.05, cd0 + max(0.0, payload_drag_delta))
    E_OSW = min(0.70, e)
    ETA_P = min(0.65, max(0.55, prop_eff))
    P_polar = aero_power_required_W(weight_N, rho, V_ms, wing_area_m2, CD0, E_OSW, wingspan_m, ETA_P)
    return hotel_W + (1.0 + install_frac) * P_polar

def gust_penalty_fraction(gustiness_index: int,
                          wind_kmh: float,
                          V_ms: float,
                          wing_loading_Nm2: float) -> float:
    """Nonlinear gust penalty. Heavier for low wing-loading + strong gusts."""
    gust_ms = max(0.0, 0.6 * float(gustiness_index))  # 0..6 m/s from slider 0..10
    V_ms = max(3.0, V_ms)
    WL = max(25.0, wing_loading_Nm2)
    WL_ref = 70.0
    base = 1.5 * (gust_ms / V_ms) ** 2 * (WL_ref / WL) ** 0.7
    wind_ms = max(0.0, wind_kmh / 3.6)
    bias = 0.03 * (wind_ms / 8.0)
    frac = max(0.0, min(0.35, base + bias))
    return frac

# ─────────────────────────────────────────────────────────
# Geometry-scaled convective/radiative thermal model
# ─────────────────────────────────────────────────────────
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
    - Only a fraction of shaft power heats the skin (~6–10%).
    - A portion of hotel load also becomes skin heat (assume 60%).
    - Convection ∝ √V and density.
    - Radiation linearized near ambient: 4 ε σ T^3.
    """
    if surface_area_m2 <= 0.0 or emissivity <= 0.0:
        return 0.0
    V_ms = max(0.5, V_ms)

    Q_skin = max(0.0, Q_shaft_W * max(0.0, power_fraction_to_skin) + hotel_W * 0.60)

    # Convection correlation
    h_nat = 6.0
    h_forced = 10.45 - V_ms + 10.0 * math.sqrt(V_ms)
    h = max(h_nat, h_forced) * (rho / RHO0)

    # Radiation
    T_ambK = ambient_C + 273.15
    rad_coeff = 4.0 * emissivity * SIGMA * (T_ambK ** 3)

    sink_W_per_K = (h + rad_coeff) * surface_area_m2
    if sink_W_per_K <= 0.0:
        return 0.0

    dT = Q_skin / sink_W_per_K
    return max(0.2, min(THERMAL_CAP_C, dT))

def climb_energy_wh(total_mass_kg: float, climb_m: float) -> float:
    """Battery climb energy m g h in Wh (1 Wh = 3600 J)."""
    if climb_m <= 0: return 0.0
    return (total_mass_kg * 9.81 * climb_m) / 3600.0

def bsfc_fuel_burn_lph(power_W: float, bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    """ICE: fuel burn (L/h) from shaft power and BSFC."""
    fuel_kg_per_h = (bsfc_gpkwh / 1000.0) * (power_W / 1000.0)
    return fuel_kg_per_h / max(0.5, fuel_density_kgpl)

def climb_fuel_liters(total_mass_kg: float, climb_m: float,
                      bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    """ICE climb fuel from m g h energy cost."""
    if climb_m <= 0: return 0.0
    E_kWh = (total_mass_kg * 9.81 * climb_m) / 3_600_000.0
    fuel_kg = (bsfc_gpkwh / 1000.0) * E_kWh
    return fuel_kg / max(0.5, fuel_density_kgpl)
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
    return SPEC_BOOK.get(model, {})

def envelope_msg(val: float, lo: float, hi: float, unit: str) -> Optional[str]:
    if val < lo:
        return f"Below conservative envelope (min {lo:g} {unit})."
    if val > hi:
        return f"Above conservative envelope (max {hi:g} {unit})."
    return None

# ─────────────────────────────────────────────────────────
# Debug toggles & platform selection
# ─────────────────────────────────────────────────────────
debug_mode = st.checkbox("Enable Debug Mode", value=False)
allow_pack_override = st.checkbox("Allow Battery Override (debug)", value=False) if debug_mode else False

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

st.info(f"**AI Capabilities:** {profile.get('ai_capabilities','—')}")
st.caption(f"Base weight: {profile['base_weight_kg']} kg — Max payload: {profile['max_payload_g']} g")
st.caption(f"Power system: `{profile['power_system']}` | Type: `{profile['type']}`")

# Dynamic flight modes:
# - Fixed-wing: Forward Flight, Loiter, Waypoint Mission (no Hover)
# - Rotor/VTOL: Hover, Forward Flight, Loiter, Waypoint Mission
if profile["type"] == "fixed":
    flight_mode_options = ["Forward Flight", "Loiter", "Waypoint Mission"]
else:
    flight_mode_options = ["Hover", "Forward Flight", "Loiter", "Waypoint Mission"]

# ─────────────────────────────────────────────────────────
# Reusable helpers used by the simulation
# ─────────────────────────────────────────────────────────
def clamp_battery(platform: Dict[str, Any], requested_wh: float, allow_override: bool) -> float:
    """Clamp requested battery to platform nominal unless override is allowed."""
    nominal = float(platform.get("battery_wh", requested_wh))
    if allow_override:
        return max(0.0, requested_wh)
    if requested_wh > nominal:
        st.warning(f"Battery clamped to platform nominal: {nominal:.0f} Wh (requested {requested_wh:.0f} Wh).")
    return max(0.0, min(requested_wh, nominal))

# ─────────────────────────────────────────────────────────
# Main input form (mission/atmosphere)
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
    stealth_drag_penalty= st.slider("Stealth Drag Factor", 1.0, 1.5, 1.0)
    simulate_failure    = st.checkbox("Enable Failure Simulation", value=False)

    # ICE panel (only when applicable)
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
        hybrid_assist     = st.checkbox("Enable Hybrid Assist (experimental)", value=False)
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
# Swarm & Stealth controls (VISIBLE before Estimate)
# ─────────────────────────────────────────────────────────
st.markdown("### Swarm & Stealth")
swarm_enable      = st.checkbox("Enable Swarm Advisor", value=True)
swarm_size        = st.slider("Swarm Size", 2, 8, 3)
swarm_steps       = st.slider("Swarm Conversation Rounds", 1, 5, 2)
stealth_ingress   = st.checkbox("Enable Stealth Ingress Mode", value=True)
threat_zone_km    = st.slider("Threat Zone Radius (km)", 1.0, 20.0, 5.0)

with st.expander("Mission Waypoints"):
    st.caption("Enter waypoints as (x,y) km coordinates relative to origin.")
    waypoint_str = st.text_area("Waypoints (e.g., 2,2; 5,0; 8,-3)", "2,2; 5,0; 8,-3")

waypoints: List[Tuple[float,float]] = []
try:
    if waypoint_str.strip():
        for pair in waypoint_str.split(";"):
            x_str, y_str = pair.split(",")
            waypoints.append((float(x_str.strip()), float(y_str.strip())))
    else:
        waypoints = [(0.0, 0.0)]
except Exception:
    st.error("Invalid waypoint format. Using (0,0).")
    waypoints = [(0.0, 0.0)]
# ─────────────────────────────────────────────────────────
# Simulation + Results (core)
# ─────────────────────────────────────────────────────────
if submitted:
    try:
        # Payload guard
        if payload_weight_g > profile["max_payload_g"]:
            st.error("Payload exceeds lift capacity."); st.stop()

        # Clamp battery unless override
        if profile["power_system"] == "Battery":
            battery_capacity_wh = clamp_battery(profile, battery_capacity_wh, allow_pack_override)

        # Basics
        total_weight_kg = profile["base_weight_kg"] + (payload_weight_g / 1000.0)
        start_batt_wh_for_gauge = battery_capacity_wh  # for live gauge consistency
        V_ms_cmd = max(0.1, (flight_speed_kmh / 3.6))
        # Optional model-specific min-speed clamp if provided in SPEC_BOOK
        V_ms = max(
            V_ms_cmd,
            SPEC_BOOK.get(drone_model, {}).get("min_airspeed_ms", 0.0)
        )
        rho, rho_ratio = density_ratio(altitude_m, temperature_c)
        weight_N = total_weight_kg * 9.81
        W_ms = max(0.0, wind_speed_kmh / 3.6)
        use_ice_branch = (profile["power_system"] == "ICE") and (ice_params is not None)

        # Battery temperature derate (simple, realistic)
        if profile["power_system"] == "Battery":
            if temperature_c < 15: battery_capacity_wh *= 0.90
            elif temperature_c > 35: battery_capacity_wh *= 0.95
            start_batt_wh_for_gauge = battery_capacity_wh

        # Atmosphere conditions
        st.header("Atmospheric Conditions")
        st.metric("Air Density ρ", f"{rho:.3f} kg/m³")
        st.metric("Density Ratio ρ/ρ₀", f"{rho_ratio:.3f}")

        # Environment factors
        st.header("Applied Environment Factors")
        if profile["type"] == "rotor":
            density_factor = rotorcraft_density_scale(rho_ratio)
            st.markdown(f"**Air density factor:** `{rho_ratio:.3f}` (ρ/ρ₀)  —  **Rotor power factor:** `{density_factor:.3f}` (∝ 1/√ρ)")
        else:
            st.markdown(f"**Air density factor:** `{rho_ratio:.3f}` (ρ/ρ₀) — handled via lift/drag in aero model.")

        # Common details bag for JSON/export panel
        detail: Dict[str, Any] = {
            "drone_model": drone_model,
            "type": profile["type"],
            "power_system": profile["power_system"],
            "payload_g": payload_weight_g,
            "total_mass_kg": round(total_weight_kg, 3),
            "weight_N": round(weight_N, 2),
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

        # ─────────────────────────────────────────────────────
        # ICE aerospace branch (e.g., MQ-1 / MQ-9)
        # ─────────────────────────────────────────────────────
        if use_ice_branch:
            # Bound unconstrained input aero params for realism
            CD0   = max(0.05, float(ice_params["cd0"]))
            E_OSW = min(0.70, float(ice_params["oswald_e"]))
            ETA_P = min(0.65, max(0.55, float(ice_params["prop_eff"])))

            # Effective loiter airspeed (fixed-wing endurance bias)
            V_ms_eff = V_ms if flight_mode != "Loiter" else max(8.0, 0.6 * V_ms)

            # Shaft power from drag polar + propulsive efficiency
            P_req_W = aero_power_required_W(
                weight_N=weight_N, rho=rho, V_ms=V_ms_eff,
                wing_area_m2=float(ice_params["wing_area_m2"]),
                cd0=CD0, e=E_OSW,
                wingspan_m=float(ice_params["wingspan_m"]), prop_eff=ETA_P
            )

            # Mission penalties
            if flight_mode == "Waypoint Mission":
                P_req_W *= 1.05
            elif flight_mode == "Loiter":
                P_req_W *= 1.10

            # Gust penalty via wing loading
            WL = weight_N / max(0.05, float(ice_params["wing_area_m2"]))
            wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms_eff, WL)
            P_req_W *= (1.0 + wind_penalty_frac)

            # Terrain & stealth (drag growth)
            P_req_W *= terrain_penalty * stealth_drag_penalty

            # Add hotel load to shaft demand
            P_total_W = P_req_W + HOTEL_W_DEFAULT

            # Fuel burn at total power
            lph = bsfc_fuel_burn_lph(
                power_W=P_total_W,
                bsfc_gpkwh=float(ice_params["bsfc_gpkwh"]),
                fuel_density_kgpl=float(ice_params["fuel_density_kgpl"])
            )

            # Climb fuel from m g h converted through BSFC
            climb_L_val = climb_fuel_liters(
                total_mass_kg=total_weight_kg,
                climb_m=max(0, elevation_gain_m),
                bsfc_gpkwh=float(ice_params["bsfc_gpkwh"]),
                fuel_density_kgpl=float(ice_params["fuel_density_kgpl"])
            )

            # Usable fuel with reserve + subtract climb
            usable_fuel_L_start = max(0.0, float(ice_params["fuel_tank_l"]) * USABLE_FUEL_FRAC - max(0.0, climb_L_val))
            usable_fuel_L = usable_fuel_L_start

            # Optional hybrid assist — battery substitutes a slice of power for a short window
            if ice_params.get("hybrid_assist", False):
                battery_support_Wh = float(profile.get("battery_wh", 200.0))
                assist_power_W = float(P_total_W) * float(ice_params["assist_fraction"])
                assist_energy_Wh = assist_power_W * (float(ice_params["assist_duration_min"]) / 60.0)
                if assist_energy_Wh > battery_support_Wh:
                    ice_params["assist_duration_min"] = (battery_support_Wh / max(1.0, assist_power_W)) * 60.0
                    assist_energy_Wh = battery_support_Wh
                saved_L_per_hr = bsfc_fuel_burn_lph(
                    power_W=assist_power_W,
                    bsfc_gpkwh=float(ice_params["bsfc_gpkwh"]),
                    fuel_density_kgpl=float(ice_params["fuel_density_kgpl"])
                )
                usable_fuel_L += saved_L_per_hr * (float(ice_params["assist_duration_min"]) / 60.0)

            # Endurance & vector-wind ranges (30% dispatch reserve)
            raw_endurance_hr   = usable_fuel_L / max(0.05, lph)
            raw_endurance_min  = raw_endurance_hr * 60.0
            dispatch_endurance_min = raw_endurance_min * (1.0 - DISPATCH_RESERVE)

            best_km, worst_km = heading_range_km(V_ms_eff, W_ms, dispatch_endurance_min)

            # Geometry-aware thermal (uses platform geometry)
            surf_area_m2 = estimate_skin_area(profile)
            delta_T = convective_radiative_deltaT_geom(
                Q_shaft_W=P_req_W, hotel_W=HOTEL_W_DEFAULT, surface_area_m2=surf_area_m2,
                emissivity=0.85, ambient_C=temperature_c, rho=rho, V_ms=V_ms_eff,
                power_fraction_to_skin=0.08  # 6–10% of shaft → skin heat
            )
            # Cloud attenuation (conservative)
            delta_T *= (1.0 - 0.20 * (cloud_cover / 100.0))

            # Detectability (AI visual / IR thermal)
            ai_score, ir_score = compute_ai_ir_scores(
                delta_T=delta_T, altitude_m=altitude_m, cloud_cover=cloud_cover,
                speed_kmh=flight_speed_kmh, gustiness=gustiness,
                stealth_factor=stealth_drag_penalty, drone_type=profile["type"],
                power_system=profile["power_system"]
            )
            overall_kind, badges_html = render_detectability_alert(ai_score, ir_score)

            # Detail panel (ICE)
            detail.update({
                "CD0_eff": CD0, "e_oswald_eff": E_OSW, "eta_prop_eff": ETA_P,
                "wing_area_m2": float(ice_params["wing_area_m2"]),
                "wingspan_m": float(ice_params["wingspan_m"]),
                "V_ms_effective": round(V_ms_eff,3),
                "wing_loading_N_per_m2": round(WL,2),
                "gust_penalty_frac": round(wind_penalty_frac,4),
                "P_req_W": round(P_req_W,1),
                "P_total_W": round(P_total_W,1),
                "BSFC_g_per_kWh": float(ice_params["bsfc_gpkwh"]),
                "fuel_density_kg_per_L": float(ice_params["fuel_density_kgpl"]),
                "fuel_burn_L_per_hr": round(lph,3),
                "climb_fuel_L": round(climb_L_val,3),
                "usable_fuel_L_start": round(usable_fuel_L_start,3),
                "usable_fuel_L_after_assist": round(usable_fuel_L,3),
                "raw_endurance_min": round(raw_endurance_min,2),
                "skin_area_m2": round(surf_area_m2,3),
                "thermal_deltaT_C": round(delta_T,1),
                "ai_visual_score_0_100": round(ai_score,1),
                "ir_thermal_score_0_100": round(ir_score,1)
            })

            wind_penalty_pct     = wind_penalty_frac * 100.0
            climb_energy_Wh_value= None
            flight_time_minutes  = dispatch_endurance_min
            climb_L              = climb_L_val

            # Totals for current selection
            total_distance_km = (flight_time_minutes / 60.0) * float(flight_speed_kmh)

            # ── UI: Detectability alert + ICE metrics ──
            st.subheader("AI/IR Detectability Alert")
            if overall_kind == "success":
                st.success("Overall detectability: LOW")
            elif overall_kind == "warning":
                st.warning("Overall detectability: MODERATE")
            else:
                st.error("Overall detectability: HIGH")
            st.markdown(badges_html, unsafe_allow_html=True)

            st.subheader("Thermal & Fuel (ICE)")
            st.metric("Total Power (shaft+hotel)", f"{P_total_W/1000:.2f} kW")
            st.metric("Fuel Burn", f"{lph:.2f} L/hr")
            st.metric("Usable Fuel (after climb/assist)", f"{usable_fuel_L:.2f} L")
            st.metric("Thermal ΔT", f"{delta_T:.1f} °C")

        # ─────────────────────────────────────────────────────
        # Battery / Hybrid branch (rotor + fixed-wing on battery)
        # ─────────────────────────────────────────────────────
        else:
            if profile["type"] == "rotor":
                # Base hover/forward-flight draw scaled by mass & density + parasitic ~V^2
                base_draw      = float(profile.get("draw_watt", 180.0))
                weight_factor  = total_weight_kg / max(0.1, float(profile["base_weight_kg"]))
                density_factor = rotorcraft_density_scale(rho_ratio)  # √(ρ0/ρ)
                V_term         = 0.018 * (flight_speed_kmh ** 2)
                total_draw     = (base_draw * weight_factor * density_factor) + V_term

                # Gust penalty (rotor WL proxy)
                WL_proxy = float(profile.get("rotor_WL_proxy", 45.0))
                wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms, WL_proxy)
                total_draw *= (1.0 + wind_penalty_frac)

                # Mission penalties
                if flight_mode == "Waypoint Mission":
                    total_draw *= 1.05
                elif flight_mode == "Loiter":
                    total_draw *= 1.08
                elif flight_mode == "Hover":
                    total_draw *= 1.10

                V_ref_ms    = V_ms
                surf_area_m2= estimate_skin_area(profile)
                detail.update({
                    "rotor_base_draw_W": base_draw,
                    "weight_factor": round(weight_factor,3),
                    "density_factor_rotor": round(density_factor,3),
                    "V_parasitic_term_W": round(V_term,2),
                    "WL_proxy": WL_proxy
                })

            else:
                # Fixed-wing on battery: bounded aero + hotel + installation losses
                wing_area_m2 = float(profile.get("wing_area_m2", 0.5))
                wingspan_m   = float(profile.get("wingspan_m", 2.0))
                cd0          = float(profile.get("cd0", 0.05))
                e            = float(profile.get("oswald_e", 0.70))
                prop_eff     = float(profile.get("prop_eff", 0.60))

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

                V_ref_ms    = V_ms_eff
                surf_area_m2= estimate_skin_area(profile)
                detail.update({
                    "wing_area_m2": wing_area_m2,
                    "wingspan_m": wingspan_m,
                    "cd0_eff": max(0.05, cd0 + (0.002 if payload_weight_g>0 else 0.0)),
                    "e_oswald_eff": min(0.70, e),
                    "eta_prop_eff": min(0.65, max(0.55, prop_eff)),
                    "V_ms_effective": round(V_ms_eff,3),
                    "wing_loading_N_per_m2": round(WL,2)
                })

            # Terrain & stealth effects (drag growth → power growth)
            total_draw *= terrain_penalty * stealth_drag_penalty

            # Climb / descent energy (battery)
            climb_energy_Wh_value = 0.0
            if elevation_gain_m > 0:
                climb_energy_Wh_value = (total_weight_kg * 9.81 * elevation_gain_m) / 3600.0
                battery_capacity_wh -= climb_energy_Wh_value
            elif elevation_gain_m < 0:
                recov = (total_weight_kg * 9.81 * abs(elevation_gain_m) / 3600.0) * 0.20
                battery_capacity_wh += recov
                detail["descent_recovery_Wh"] = round(recov,2)

            # Usable energy + dispatch reserve
            batt_temp_derated_Wh = battery_capacity_wh
            usable_Wh = max(0.0, batt_temp_derated_Wh) * USABLE_BATT_FRAC
            t_raw_min = (usable_Wh / max(5.0, total_draw)) * 60.0
            dispatch_endurance_min = t_raw_min * (1.0 - DISPATCH_RESERVE)

            # Vector wind ranges using reference airspeed
            best_km, worst_km = heading_range_km(V_ref_ms, W_ms, dispatch_endurance_min)

            # Geometry-aware thermal for battery platforms
            delta_T = convective_radiative_deltaT_geom(
                Q_shaft_W=max(0.0, total_draw - HOTEL_W_DEFAULT),  # aero/prop part
                hotel_W=HOTEL_W_DEFAULT, surface_area_m2=surf_area_m2,
                emissivity=0.90, ambient_C=temperature_c, rho=rho, V_ms=V_ref_ms,
                power_fraction_to_skin=0.08
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
                "skin_area_m2": round(surf_area_m2,3),
                "thermal_deltaT_C": round(delta_T,1),
                "ai_visual_score_0_100": round(ai_score,1),
                "ir_thermal_score_0_100": round(ir_score,1)
            })

            wind_penalty_pct     = wind_penalty_frac * 100.0
            flight_time_minutes  = dispatch_endurance_min
            climb_L              = None
            total_distance_km    = (flight_time_minutes / 60.0) * float(flight_speed_kmh)

            # ── UI: Detectability alert + Battery metrics ──
            st.subheader("AI/IR Detectability Alert")
            if overall_kind == "success":
                st.success("Overall detectability: LOW")
            elif overall_kind == "warning":
                st.warning("Overall detectability: MODERATE")
            else:
                st.error("Overall detectability: HIGH")
            st.markdown(badges_html, unsafe_allow_html=True)

            st.subheader("Thermal Signature & Battery")
            risk = 'Low' if delta_T < 10 else ('Moderate' if delta_T < 20 else 'High')
            st.metric("Thermal Signature Risk", f"{risk} (ΔT = {delta_T:.1f}°C)")
            st.metric("Total Draw (incl. hotel/penalties)", f"{total_draw:.0f} W")

        # ─────────────────────────────────────────────────────
        # Mission performance metrics (shared)
        # ─────────────────────────────────────────────────────
        lo = flight_time_minutes * 0.90
        hi = flight_time_minutes * 1.10

        st.header("Selected UAV — Mission Performance")
        st.metric("Dispatchable Endurance", f"{flight_time_minutes:.1f} minutes")
        st.caption(f"Uncertainty band: {lo:.1f}–{hi:.1f} min (±10%)")
        st.metric("Total Distance (km)", f"{total_distance_km:.1f} km")
        st.metric("Best Heading Range", f"{best_km:.1f} km")
        st.metric("Upwind Range", f"{worst_km:.1f} km")

        # ─────────────────────────────────────────────────────
        # Detailed panel (human summary) + machine-readable JSON
        # ─────────────────────────────────────────────────────
        st.header("Individual UAV Detailed Results (Selected Model)")
        human = []
        human.append(f"- **Model**: {drone_model} ({profile['type']}, {profile['power_system']})")
        human.append(f"- **Payload used**: {payload_weight_g} g (max {profile['max_payload_g']} g)")
        human.append(f"- **Mass**: {total_weight_kg:.3f} kg → **Weight**: {weight_N:.1f} N")
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
        human.append(f"- **Thermal ΔT (geometry-scaled)**: {detail.get('thermal_deltaT_C', 0):.1f} °C")
        human.append(f"- **Dispatchable Endurance**: {flight_time_minutes:.1f} min")
        human.append(f"- **Total Distance (km)**: {total_distance_km:.2f} km")
        human.append(f"- **Best heading / Upwind ranges**: {best_km:.2f} km / {worst_km:.2f} km")
        human.append(f"- **Detectability (AI visual / IR thermal)**: {detail.get('ai_visual_score_0_100',0):.0f}/100 / {detail.get('ir_thermal_score_0_100',0):.0f}/100")
        human.append(f"- **Overall Detectability**: {'LOW' if (use_ice_branch or True) and ('success' in locals() and overall_kind=='success') else ('MODERATE' if overall_kind=='warning' else 'HIGH')}")
        st.markdown("\n".join(human))

        # Machine-readable JSON
        detail.update({
            "dispatch_endurance_min": round(flight_time_minutes,1),
            "total_distance_km": round(total_distance_km,2),
            "best_heading_range_km": round(best_km,2),
            "upwind_range_km": round(worst_km,2),
            "wind_penalty_%": round(wind_penalty_pct,1),
        })
        st.json(detail, expanded=False)

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)
# ─────────────────────────────────────────────────────────
# Specs, geometry helpers, and thermal wrapper (shared)
# ─────────────────────────────────────────────────────────
THERMAL_CAP_C = 35.0  # cap geometry-scaled ΔT for realism/UX

# Broad, conservative envelopes (for sanity checks & speed clamp)
SPEC_BOOK: Dict[str, Dict[str, Any]] = {
    "Generic Quad":           {"endurance_range_hr": (0.2, 0.6), "cruise_kmh_range": (10, 45)},
    "DJI Phantom":            {"endurance_range_hr": (0.35, 0.6), "cruise_kmh_range": (20, 50)},
    "Skydio 2+":              {"endurance_range_hr": (0.3, 0.5), "cruise_kmh_range": (10, 45)},
    "Freefly Alta 8":         {"endurance_range_hr": (0.2, 0.5), "cruise_kmh_range": (10, 40)},
    "RQ-11 Raven":            {"endurance_range_hr": (1.0, 1.5), "cruise_kmh_range": (30, 80), "min_airspeed_ms": 10.0},
    "RQ-20 Puma":             {"endurance_range_hr": (2.0, 3.5), "cruise_kmh_range": (35, 90), "min_airspeed_ms": 12.0},
    "Teal Golden Eagle":      {"endurance_range_hr": (0.8, 1.5), "cruise_kmh_range": (40, 110), "min_airspeed_ms": 14.0},
    "Quantum Systems Vector": {"endurance_range_hr": (1.5, 3.0), "cruise_kmh_range": (45, 90), "min_airspeed_ms": 12.0},
    "MQ-1 Predator":          {"endurance_range_hr": (12, 24),  "cruise_kmh_range": (100, 220), "min_airspeed_ms": 28.0},
    "MQ-9 Reaper":            {"endurance_range_hr": (14, 27),  "cruise_kmh_range": (150, 350), "min_airspeed_ms": 30.0},
    "Custom Build":           {"endurance_range_hr": (0.3, 2.0), "cruise_kmh_range": (20, 80)}
}

def spec_for(model: str) -> Dict[str, Any]:
    return SPEC_BOOK.get(model, {})

def envelope_msg(val: float, lo: float, hi: float, unit: str) -> Optional[str]:
    if val < lo:
        return f"below typical envelope (min {lo:.1f} {unit})"
    if val > hi:
        return f"above typical envelope (max {hi:.1f} {unit})"
    return None

def estimate_skin_area(profile: Dict[str, Any]) -> float:
    """
    Rough wetted area estimate from basic geometry in profile.
    - Fixed-wing: ~2.6 * wing area + small fuselage bias from span
    - Rotor: body proxy from base mass; large rotors don't radiate like skin, so keep small
    """
    if profile.get("type") == "fixed" and "wing_area_m2" in profile:
        S = float(profile.get("wing_area_m2", 0.5))
        b = float(profile.get("wingspan_m", 2.0))
        return max(0.25, 2.6 * S + 0.12 * b)
    # rotorcraft body proxy
    m = float(profile.get("base_weight_kg", 1.5))
    return max(0.20, 0.18 * (m ** 0.85))

def convective_radiative_deltaT_geom(
    Q_shaft_W: float,
    hotel_W: float,
    surface_area_m2: float,
    emissivity: float,
    ambient_C: float,
    rho: float,
    V_ms: float,
    power_fraction_to_skin: float = 0.08
) -> float:
    """
    Geometry-aware wrapper: fraction of aero/shaft power + electronics 'hotel' becomes skin heat.
    Then run the robust convective+radiative sink and cap for UX stability.
    """
    Q_w = max(0.0, hotel_W) + max(0.0, Q_shaft_W) * max(0.0, min(0.5, power_fraction_to_skin))
    dT = convective_radiative_deltaT(Q_w, max(0.05, surface_area_m2), max(0.5, emissivity),
                                     ambient_C, rho, max(0.5, V_ms))
    return min(THERMAL_CAP_C, dT)


# ─────────────────────────────────────────────────────────
# Failsafe: ensure Swarm & Stealth controls appear pre-submit
# (Only rendered if earlier UI didn’t already define them)
# ─────────────────────────────────────────────────────────
if "swarm_enable" not in globals():
    st.markdown("### Swarm & Stealth")
    swarm_enable    = st.checkbox("Enable Swarm Advisor", value=True)
    swarm_size      = st.slider("Swarm Size", 2, 8, 3)
    swarm_steps     = st.slider("Swarm Conversation Rounds", 1, 5, 2)
    stealth_ingress = st.checkbox("Enable Stealth Ingress Mode", value=True)
    threat_zone_km  = st.slider("Threat Zone Radius (km)", 1.0, 20.0, 5.0)
    with st.expander("Mission Waypoints"):
        st.caption("Enter waypoints as (x,y) km coordinates relative to origin.")
        waypoint_str = st.text_area("Waypoints (e.g., 2,2; 5,0; 8,-3)", "2,2; 5,0; 8,-3")
    waypoints = []
    try:
        for pair in waypoint_str.split(";"):
            x_str, y_str = pair.split(",")
            waypoints.append((float(x_str.strip()), float(y_str.strip())))
    except Exception:
        st.error("Invalid waypoint format. Using (0,0).")
        waypoints = [(0.0, 0.0)]


# ─────────────────────────────────────────────────────────
# Post-simulation UI (append after Part 4’s detail panel)
# ─────────────────────────────────────────────────────────
if submitted:
    try:
        # ───── Sanity Checks (non-blocking) ─────
        st.subheader("Sanity Checks (non-blocking)")
        checks = []
        spec = spec_for(drone_model)

        # Endurance vs platform envelope
        end_hr = max(0.0, float(flight_time_minutes) / 60.0)
        if "endurance_range_hr" in spec:
            loE, hiE = spec["endurance_range_hr"]
            msg = envelope_msg(end_hr, loE, hiE, "hr")
            if msg:
                checks.append(("Endurance", f"{end_hr:.2f} hr — {msg}"))

        # Cruise speed vs platform envelope (use ground speed entered)
        if "cruise_kmh_range" in spec:
            loV, hiV = spec["cruise_kmh_range"]
            msg = envelope_msg(float(flight_speed_kmh), loV, hiV, "km/h")
            if msg:
                checks.append(("Speed", f"{float(flight_speed_kmh):.0f} km/h — {msg}"))

        # Thermal realism guard (near cap)
        if "thermal_deltaT_C" in detail and float(detail["thermal_deltaT_C"]) >= THERMAL_CAP_C * 0.95:
            checks.append(("Thermal", f"ΔT={float(detail['thermal_deltaT_C']):.1f}°C near cap ({THERMAL_CAP_C}°C). Geometry/power share may be conservative."))

        # ICE fuel burn plausibility (broad)
        if 'use_ice_branch' in locals() and use_ice_branch and 'lph' in locals():
            if not (0.5 <= float(lph) <= 120.0):
                checks.append(("Fuel Burn", f"{float(lph):.2f} L/h outside wide plausibility band (0.5–120). Check weights/drag/BSFC."))

        if not checks:
            st.success("All results fall within conservative envelopes.")
        else:
            for title, msg in checks:
                st.warning(f"**{title}:** {msg}")

        # ───── Export Scenario Summary (CSV + JSON + copy) ─────
        st.subheader("Export Scenario Summary")
        results = {
            "Drone Model": drone_model,
            "Power System": profile["power_system"],
            "Type": profile["type"],
            "Flight Mode": flight_mode,
            "Battery Capacity (Wh)": round(battery_capacity_wh, 2) if profile["power_system"]=="Battery" else float(profile.get("battery_wh", 0)),
            "Payload (g)": int(payload_weight_g),
            "Speed (km/h)": float(flight_speed_kmh),
            "Wind (km/h)": float(wind_speed_kmh),
            "Gustiness (0-10)": int(gustiness),
            "Altitude (m)": int(altitude_m),
            "Air Density (kg/m³)": round(float(detail.get("rho", 0.0)), 3),
            "Density Ratio (ρ/ρ0)": round(float(detail.get("rho_ratio", 0.0)), 3),
            "Wind Penalty (%)": round(float(wind_penalty_pct), 1),
            "Climb Energy (Wh)": round(float(detail.get("climb_energy_Wh", 0.0)), 2) if profile["power_system"]=="Battery" else None,
            "Climb Fuel (L)": round(float(climb_L), 2) if 'climb_L' in locals() and climb_L is not None else None,
            "Dispatchable Endurance (min)": round(float(flight_time_minutes), 1),
            "Total Distance (km)": round(float(total_distance_km), 2),
            "Best Heading Range (km)": round(float(best_km), 2),
            "Upwind Range (km)": round(float(worst_km), 2),
            "ΔT (°C)": round(float(detail.get("thermal_deltaT_C", 0.0)), 1),
            "AI Visual Detectability (0-100)": round(float(detail.get("ai_visual_score_0_100", 0.0)), 1),
            "IR Thermal Detectability (0-100)": round(float(detail.get("ir_thermal_score_0_100", 0.0)), 1),
            "Overall Detectability": detail.get("detectability_overall") or ("LOW" if 'overall_kind' in locals() and overall_kind=='success' else ("MODERATE" if 'overall_kind' in locals() and overall_kind=='warning' else "HIGH"))
        }

        df_res = pd.DataFrame([results])
        csv_bytes = df_res.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Scenario Summary (CSV)",
            data=csv_bytes,
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

        # ───── AI Mission Advisor (LLM) ─────
        st.subheader("AI Mission Advisor (LLM)")
        if "generate_llm_advice" not in globals():
            # Fallback definition (won't override if already present)
            def generate_llm_advice(params):
                return ("LLM unavailable — heuristic advice:\n"
                        "- Fly near best-endurance speed.\n"
                        "- Descend 100–200 m if gusts rise.\n"
                        "- Reduce payload for margin.\n"
                        "- Use cloud cover to mask IR.")
        params = {
            "drone":drone_model, "payload_g":payload_weight_g, "mode":flight_mode,
            "speed_kmh":flight_speed_kmh, "alt_m":altitude_m,
            "wind_kmh":wind_speed_kmh, "gust":gustiness,
            "endurance_min":flight_time_minutes, "delta_T":float(detail.get("thermal_deltaT_C", 0.0)),
            "fuel_l": float(detail.get("usable_fuel_L_after_assist", 0.0)) if ('use_ice_branch' in locals() and use_ice_branch) else 0.0,
            "hybrid_assist": (('use_ice_branch' in locals() and use_ice_branch) and bool(locals().get('ice_params', {}).get('hybrid_assist', False))),
            "assist_fraction": float(locals().get('ice_params', {}).get('assist_fraction', 0.0)) if ('use_ice_branch' in locals() and use_ice_branch) else 0.0,
            "assist_duration_min": int(locals().get('ice_params', {}).get('assist_duration_min', 0)) if ('use_ice_branch' in locals() and use_ice_branch) else 0
        }
        st.write(generate_llm_advice(params))

        # ───── Swarm Advisor (Multi-Agent) + Playback + Exports ─────
        if 'swarm_enable' in globals() and swarm_enable:
            # Ensure required swarm helpers exist (from earlier part); if not, soft-disable.
            required = all(name in globals() for name in ["seed_swarm","agent_call","lead_call","apply_actions","plot_swarm_map","AgentState"])
            if not required:
                st.info("Swarm modules not loaded. Make sure Part 3 (Swarm scaffolding) is included.")
            else:
                st.header("Swarm Advisor (Multi-Agent LLM)")

                base_endurance = float(max(5.0, flight_time_minutes))
                base_batt_wh = float(max(10.0, (battery_capacity_wh if profile["power_system"]=="Battery" else 200.0)))

                swarm = seed_swarm(swarm_size, base_endurance, base_batt_wh,
                                   float(detail.get("thermal_deltaT_C", 0.0)),
                                   int(altitude_m), platform=drone_model)
                for s in swarm:
                    s.waypoints = waypoints.copy() if 'waypoints' in globals() else []
                    s.current_wp = 0

                st.write("**Initial Swarm State**")
                for s in swarm:
                    st.write(f"- {s.id} [{s.role}] ({s.platform}) — End {s.endurance_min:.1f} min | "
                             f"Fuel {s.fuel_l:.1f} L | Alt {s.altitude_m} m | Pos ({s.x_km:+.1f},{s.y_km:+.1f}) km | ΔT {s.delta_T:.1f}°C")

                env = {
                    "wind_kmh": wind_speed_kmh, "gust": gustiness, "mission": flight_mode,
                    "threat_note": ("elevated" if (simulate_failure or float(detail.get("thermal_deltaT_C", 0.0)) > 15 or altitude_m > 100) else "normal"),
                    "stealth_ingress": stealth_ingress, "threat_zone_km": threat_zone_km
                }

                for round_idx in range(int(swarm_steps)):
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

                # Playback with simple waypoint following
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
                        s.fuel_l = max(0, s.fuel_l - (random.uniform(0.6, 1.6) if "MQ-" in s.platform else random.uniform(0.1, 0.5)))
                        if stealth_ingress and s.platform in ["MQ-1 Predator","MQ-9 Reaper"] and ((s.x_km**2 + s.y_km**2)**0.5 <= threat_zone_km):
                            s.hybrid_assist = True; s.assist_fraction = 0.15; s.assist_time_min = 10
                            s.delta_T *= (1 - 0.15*0.7); s.warning = "Auto Hybrid Assist (Stealth Ingress)"
                        snapshot.append(asdict(s))
                    swarm_history.append(snapshot)

                frame = st.slider("Mission Time (minutes)", 0, timesteps-1, 0)
                frame_swarm = [AgentState(**data) for data in swarm_history[frame]]

                for s in frame_swarm:
                    assist_txt = f" [Assist {s.assist_fraction*100:.0f}% {s.assist_time_min:.0f} min]" if s.hybrid_assist else ""
                    zone_flag = "🟥 IN ZONE" if (stealth_ingress and ((s.x_km**2 + s.y_km**2)**0.5 <= threat_zone_km)) else ""
                    alert = f" ⚠ {s.warning}" if s.warning else ""
                    st.write(f"- {s.id} [{s.role}] — End {s.endurance_min:.1f} min | Fuel {s.fuel_l:.1f} L | Alt {s.altitude_m} m | ΔT {s.delta_T:.1f}°C{assist_txt}{alert} {zone_flag}")

                fig = plot_swarm_map(frame_swarm, threat_zone_km, stealth_ingress, waypoints if 'waypoints' in globals() else None)
                st.pyplot(fig)
                plt.close(fig)

                # CSV exports for playback
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
                if 'waypoints' in globals() and waypoints:
                    wp_df = pd.DataFrame(waypoints, columns=["x_km","y_km"])
                    st.download_button(
                        "Download Mission Waypoints CSV",
                        data=wp_df.to_csv(index=False).encode("utf-8"),
                        file_name="mission_waypoints.csv",
                        mime="text/csv"
                    )

        # (Optional) simple heuristic suggestions — keep if not shown earlier
        if 'suggestions_shown' not in st.session_state:
            st.subheader("AI Suggestions (Heuristics)")
            if payload_weight_g == profile["max_payload_g"]:
                st.write("**Tip:** Payload is at maximum lift capacity.")
            if wind_speed_kmh > 15:
                st.write("**Tip:** High wind may reduce flight time and upwind range.")
            if profile["power_system"]=="Battery" and battery_capacity_wh < 30:
                st.write("**Tip:** Battery is under 30 Wh. Consider a larger pack.")
            if flight_mode in ["Hover", "Waypoint Mission", "Loiter"]:
                st.write("**Tip:** Maneuvering or station-keeping increases power draw; plan extra reserve.")
            if stealth_drag_penalty > 1.2:
                st.write("**Tip:** Stealth loadout may reduce endurance.")
            if float(detail.get("thermal_deltaT_C", 0.0)) > 15:
                st.write("**Tip:** Thermal load is high. Consider lighter payload or lower altitude.")
            if altitude_m > 100:
                st.write("**Tip:** Flying above 100 m may increase detection risk.")
            if gustiness >= 5:
                st.write("**Tip:** Gust factor above 5 may destabilize small UAVs.")
            st.session_state['suggestions_shown'] = True

    except Exception as e:
        st.error("Unexpected error in post-simulation pipeline.")
        if 'debug_mode' in globals() and debug_mode:
            st.exception(e)
    
