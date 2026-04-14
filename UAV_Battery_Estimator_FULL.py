# app_production.py
from __future__ import annotations

import io
import json
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

OPENAI_AVAILABLE = False
_client = None
try:
    from openai import OpenAI
    _client = OpenAI()
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False
    _client = None

st.set_page_config(page_title='UAV Battery Efficiency Estimator', page_icon='🛰️', layout='wide')
st.markdown("<h1 style='color:#00FF00;'>UAV Battery Efficiency Estimator</h1>", unsafe_allow_html=True)
st.caption('Production build — first-order aerospace performance modeling, swarm simulation, and mission planning dashboard')

st.markdown("""
<style>
:root {
  --bg: #0b1220;
  --panel: #121a2b;
  --panel-2: #172033;
  --text: #e6edf7;
  --muted: #9fb0c7;
  --accent: #22c55e;
  --accent-2: #38bdf8;
  --border: #22304a;
  --warning: #f59e0b;
  --danger: #ef4444;
}
.stApp {
  background: linear-gradient(180deg, #0a0f1a 0%, var(--bg) 100%);
  color: var(--text);
}
h1, h2, h3 {
  color: var(--accent) !important;
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0f1727 0%, #0c1320 100%);
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] * {
  color: var(--text) !important;
}
div[data-testid="stMetric"] {
  background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.18);
}
.section-card {
  background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px 16px 10px 16px;
  margin-bottom: 12px;
}
.section-title {
  color: var(--accent);
  font-size: 1.08rem;
  font-weight: 800;
  margin-bottom: 4px;
}
.section-note {
  color: var(--muted);
  font-size: 0.94rem;
  line-height: 1.5;
}
.status-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  margin: 8px 0 14px 0;
}
.status-tile {
  background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px 12px;
}
.status-label {
  color: var(--accent);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.status-value {
  color: var(--text);
  font-size: 0.95rem;
  font-weight: 700;
}
.status-ok { color: var(--accent); }
.status-warn { color: var(--warning); }
.status-danger { color: var(--danger); }
@media (max-width: 900px) {
  .status-strip { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# Theme-aware chart helpers
# =========================================================
THEME = {
    "dark": {
        "bg": "#0b1220",
        "panel": "#121a2b",
        "grid": "#26354f",
        "text": "#e6edf7",
        "muted": "#9fb0c7",
        "accent": "#22c55e",
        "accent2": "#38bdf8",
        "warning": "#f59e0b",
        "danger": "#ef4444",
        "path": "#94a3b8",
    },
    "light": {
        "bg": "#f4f7fb",
        "panel": "#ffffff",
        "grid": "#d8e1ee",
        "text": "#152033",
        "muted": "#5f7188",
        "accent": "#0f62fe",
        "accent2": "#f97316",
        "warning": "#d97706",
        "danger": "#dc2626",
        "path": "#64748b",
    },
}
# Global UI theme selector must be defined before ACTIVE_THEME
theme_mode = st.sidebar.radio(
    'UI Theme',
    ['Aerospace Dark', 'Engineering Light'],
    index=0,
)

ACTIVE_THEME = THEME["dark"] if theme_mode == "Aerospace Dark" else THEME["light"]

def style_axes(ax):
    ax.set_facecolor(ACTIVE_THEME["panel"])
    for spine in ax.spines.values():
        spine.set_color(ACTIVE_THEME["grid"])
    ax.tick_params(colors=ACTIVE_THEME["text"])
    ax.xaxis.label.set_color(ACTIVE_THEME["text"])
    ax.yaxis.label.set_color(ACTIVE_THEME["text"])
    ax.title.set_color(ACTIVE_THEME["text"])
    ax.grid(True, color=ACTIVE_THEME["grid"], alpha=0.35, linewidth=0.8)
    return ax

def make_themed_figure(figsize=(5, 5)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(ACTIVE_THEME["bg"])
    ax.set_facecolor(ACTIVE_THEME["panel"])
    return fig, ax

def render_status_strip(platform_type: str, power_system: str, theme_name: str, caution_label: str, caution_class: str):
    return f"""
    <div class='status-strip'>
        <div class='status-tile'>
            <div class='status-label'>Platform Type</div>
            <div class='status-value'>{platform_type.title()}</div>
        </div>
        <div class='status-tile'>
            <div class='status-label'>Power System</div>
            <div class='status-value'>{power_system}</div>
        </div>
        <div class='status-tile'>
            <div class='status-label'>Theme</div>
            <div class='status-value'>{theme_name}</div>
        </div>
        <div class='status-tile'>
            <div class='status-label'>Mission Status</div>
            <div class='status-value {caution_class}'>{caution_label}</div>
        </div>
    </div>
    """
st.info(
    'This tool uses first-order physics and bounded heuristics. '
    'It is not a validated flight-performance or EO/IR sensor model.'
)

RHO0 = 1.225
P0 = 101325.0
T0_STD = 288.15
LAPSE = 0.0065
R_AIR = 287.05
G0 = 9.80665
SIGMA_SB = 5.670374419e-8

USABLE_BATT_FRAC = 0.85
USABLE_FUEL_FRAC = 0.90
DISPATCH_RESERVE = 0.30
HOTEL_W_DEFAULT = 15.0

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def numeric_input(label: str, default: float) -> float:
    val_str = st.text_input(label, value=str(default))
    if val_str.strip() == '':
        return default
    try:
        return float(val_str)
    except ValueError:
        st.error(f'Invalid number for {label}. Using default {default}.')
        return default

def clamp_battery(platform: Dict[str, Any], requested_wh: float, allow_override: bool) -> float:
    nominal = float(platform.get('battery_wh', requested_wh))
    if allow_override:
        return max(0.0, requested_wh)
    if requested_wh > nominal:
        st.warning(f'Battery clamped to platform nominal: {nominal:.0f} Wh.')
    return max(0.0, min(requested_wh, nominal))

def isa_density_troposphere(alt_m: float, delta_isa_C: float = 0.0) -> Tuple[float, float, float]:
    h = max(0.0, alt_m)
    T_std = T0_STD - LAPSE * h
    p = P0 * (T_std / T0_STD) ** (G0 / (R_AIR * LAPSE))
    T = max(150.0, T_std + delta_isa_C)
    rho = p / (R_AIR * T)
    return T, p, rho

def density_ratio_from_ambient(alt_m: float, ambient_C: float) -> Tuple[float, float]:
    h = max(0.0, alt_m)
    T_std_alt_C = (T0_STD - LAPSE * h) - 273.15
    delta_isa_C = ambient_C - T_std_alt_C
    _, _, rho = isa_density_troposphere(h, delta_isa_C)
    return rho, rho / RHO0

def heading_range_km(V_air_ms: float, W_ms: float, t_min: float) -> Tuple[float, float]:
    t_s = max(0.0, t_min) * 60.0
    if V_air_ms <= 0.1:
        return 0.0, 0.0
    best_gs = V_air_ms + max(0.0, W_ms)
    if W_ms >= V_air_ms:
        return best_gs * t_s / 1000.0, 0.0
    worst_gs = V_air_ms - max(0.0, W_ms)
    return best_gs * t_s / 1000.0, worst_gs * t_s / 1000.0

def battery_temp_capacity_factor(temp_c: float) -> float:
    if temp_c <= -10:
        return 0.65
    if temp_c <= 0:
        return 0.78
    if temp_c <= 10:
        return 0.88
    if temp_c <= 30:
        return 1.00
    if temp_c <= 40:
        return 0.96
    return 0.92

def climb_energy_wh(total_mass_kg: float, climb_m: float, eta_climb: float = 0.75) -> float:
    if climb_m <= 0.0:
        return 0.0
    return (total_mass_kg * G0 * climb_m) / (3600.0 * max(0.3, eta_climb))

def climb_fuel_liters(total_mass_kg: float, climb_m: float, bsfc_gpkwh: float, fuel_density_kgpl: float, eta_climb: float = 0.70) -> float:
    if climb_m <= 0.0:
        return 0.0
    E_kWh = (total_mass_kg * G0 * climb_m) / (3_600_000.0 * max(0.3, eta_climb))
    fuel_kg = (bsfc_gpkwh / 1000.0) * E_kWh
    return fuel_kg / max(0.5, fuel_density_kgpl)

def drag_polar_cd(cd0: float, cl: float, e: float, aspect_ratio: float) -> float:
    e_eff = clamp(e, 0.5, 0.95)
    ar_eff = max(2.0, aspect_ratio)
    k = 1.0 / (math.pi * e_eff * ar_eff)
    return cd0 + k * cl * cl

def prop_efficiency_map(advance_factor: float, eta_nominal: float, power_system: str = 'Battery') -> float:
    """
    First-order educational propulsor efficiency abstraction.
    Less punitive at higher advance factors for larger ICE / turboprop aircraft.
    """
    eta_peak = clamp(eta_nominal, 0.45, 0.90)
    if power_system == 'ICE':
        penalty = 0.04 * abs(advance_factor - 1.0)
        eta_floor = 0.70
    else:
        penalty = 0.10 * abs(advance_factor - 1.0)
        eta_floor = 0.40
    return clamp(eta_peak - penalty, eta_floor, eta_peak)

def fixedwing_power_required(weight_N: float, rho: float, V_ms: float, wing_area_m2: float, span_m: float, cd0: float, e: float, prop_eff: float, power_system: str, hotel_W: float = HOTEL_W_DEFAULT, install_frac: float = 0.10, cl_max: float = 1.4) -> Dict[str, float]:
    V = max(8.0, V_ms)
    S = max(1e-4, wing_area_m2)
    b = max(0.1, span_m)
    cd0_eff = max(0.015, cd0)
    q = 0.5 * rho * V * V
    AR = (b * b) / S
    cl = weight_N / max(1e-6, q * S)
    cd = drag_polar_cd(cd0_eff, cl, e, AR)
    drag_N = q * S * cd
    V_ref = 25.0
    eta_p = prop_efficiency_map(V / V_ref, prop_eff, power_system=power_system)
    shaft_W = (drag_N * V) / eta_p
    total_W = hotel_W + shaft_W * (1.0 + max(0.0, install_frac))
    return {'q_Pa': q, 'AR': AR, 'CL': cl, 'CD': cd, 'drag_N': drag_N, 'eta_prop_eff': eta_p, 'shaft_W': shaft_W, 'total_W': total_W, 'stall_margin_ok': 1.0 if cl <= cl_max else 0.0}

def fixedwing_endurance_minutes(battery_wh: float, total_draw_W: float, reserve_frac: float = DISPATCH_RESERVE, usable_frac: float = USABLE_BATT_FRAC) -> float:
    usable_Wh = max(0.0, battery_wh) * usable_frac
    raw_min = (usable_Wh / max(1.0, total_draw_W)) * 60.0
    return raw_min * (1.0 - reserve_frac)

def rotor_power_required(gross_mass_kg: float, rho_ratio: float, speed_kmh: float, hover_power_W_ref: float, parasitic_area_m2: float = 0.03, cd_body: float = 1.0, hotel_W: float = HOTEL_W_DEFAULT) -> Dict[str, float]:
    V = max(0.0, speed_kmh / 3.6)
    sigma = max(0.3, rho_ratio)
    induced_hover_W = max(1.0, hover_power_W_ref) / math.sqrt(sigma)
    induced_forward_factor = 1.0 / math.sqrt(1.0 + (V / 12.0) ** 2)
    induced_W = induced_hover_W * induced_forward_factor
    profile_W = 0.18 * induced_hover_W
    q = 0.5 * RHO0 * V * V
    parasite_drag_N = q * max(0.001, parasitic_area_m2) * max(0.2, cd_body)
    parasite_W = parasite_drag_N * V
    total_W = induced_W + profile_W + parasite_W + hotel_W
    return {'induced_W': induced_W, 'profile_W': profile_W, 'parasite_W': parasite_W, 'hover_W': induced_hover_W, 'total_W': total_W}

def mission_gust_penalty_fraction(gustiness_index: int, wind_kmh: float, V_ms: float, wing_loading_Nm2: float) -> float:
    gust_ms = max(0.0, 0.6 * float(gustiness_index))
    V = max(4.0, V_ms)
    WL = max(20.0, wing_loading_Nm2)
    base = 0.9 * (gust_ms / V) ** 2 * (70.0 / WL) ** 0.6
    wind_bias = 0.02 * ((max(0.0, wind_kmh) / 3.6) / 8.0)
    return clamp(base + wind_bias, 0.0, 0.30)

def bsfc_fuel_burn_lph(power_W: float, bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    fuel_kgph = (max(0.0, bsfc_gpkwh) / 1000.0) * (max(0.0, power_W) / 1000.0)
    return fuel_kgph / max(0.5, fuel_density_kgpl)

def convective_deltaT_simple(waste_heat_W: float, surface_area_m2: float, ambient_C: float, rho: float, V_ms: float, emissivity: float = 0.90) -> float:
    if waste_heat_W <= 0.0 or surface_area_m2 <= 0.0:
        return 0.0
    V = max(0.5, V_ms)
    h = max(6.0, 10.45 - V + 10.0 * math.sqrt(V)) * max(0.4, rho / RHO0)
    T_ambK = ambient_C + 273.15
    rad_coeff = 4.0 * emissivity * SIGMA_SB * (T_ambK ** 3)
    sink_per_K = (h + rad_coeff) * surface_area_m2
    dT = waste_heat_W / max(1.0, sink_per_K)
    return max(0.0, dT)

DEFAULT_SIZE_M = {'Generic Quad': 0.45, 'DJI Phantom': 0.35, 'Skydio 2+': 0.30, 'Freefly Alta 8': 1.30, 'Teal 2 / Golden Eagle': 0.50, 'RQ-11 Raven': 1.40, 'RQ-20 Puma': 2.80, 'Vector AI (Fixed-Wing)': 2.80, 'Vector AI (Multicopter)': 2.20, 'MQ-1 Predator': 14.8, 'MQ-9 Reaper': 20.0, 'Custom Build': 1.00}

def _risk_bucket(score: float) -> Tuple[str, str, str]:
    if score < 33:
        return ('Low', 'success', '#0f9d58')
    if score < 67:
        return ('Moderate', 'warning', '#f4b400')
    return ('High', 'error', '#db4437')

def _badge(label: str, score: float, bg: str) -> str:
    return f"<span style='display:inline-block;padding:6px 10px;margin-right:8px;border-radius:8px;background:{bg};color:#fff;font-weight:600;font-size:13px;white-space:nowrap;'>{label}: {score:.0f}/100</span>"

def compute_detectability_scores_v3(
    delta_T: float,
    altitude_m: float,
    speed_kmh: float,
    cloud_cover: int,
    gustiness: int,
    stealth_factor: float,
    drone_type: str,
    power_system: str,
    effective_size_m: float,
    background_complexity: float,
    humidity_factor: float = 0.5,
) -> dict:
    """
    Heuristic mission-awareness model only.
    Not a validated EO/IR sensor model.
    """

    size_term = clamp01(effective_size_m / 3.0)
    altitude_term = 1.0 - min(0.80, altitude_m / 1200.0)
    speed_term = clamp01(speed_kmh / 90.0)
    motion_bonus = 0.18 if drone_type == "rotor" else 0.08

    clutter_reduction = 1.0 - 0.35 * clamp01(background_complexity)
    cloud_reduction = 1.0 - 0.18 * (cloud_cover / 100.0)
    humidity_reduction = 1.0 - 0.10 * clamp01(humidity_factor)
    stealth_reduction = 1.0 - max(0.0, (stealth_factor - 1.0) * 0.18)

    visual_raw = (
        0.36 * size_term +
        0.30 * altitude_term +
        0.16 * speed_term +
        0.10 * motion_bonus
    )

    visual_score = 100.0 * clamp01(
        visual_raw *
        clutter_reduction *
        cloud_reduction *
        humidity_reduction *
        stealth_reduction
    )

    thermal_contrast = clamp01(delta_T / 25.0)
    exposed_size = clamp01(effective_size_m / 2.5)

    altitude_reduction = 1.0 - min(0.50, altitude_m / 2000.0)
    cloud_ir_reduction = 1.0 - 0.22 * (cloud_cover / 100.0)
    humidity_ir_reduction = 1.0 - 0.18 * clamp01(humidity_factor)
    atmosphere_factor = max(0.45, cloud_ir_reduction * humidity_ir_reduction)

    propulsion_bias = 0.12 if power_system == "ICE" else 0.03
    thermal_speed_term = 0.06 * clamp01(speed_kmh / 120.0)
    gust_uncertainty = 1.0 - 0.04 * (gustiness / 10.0)

    thermal_raw = (
        0.56 * thermal_contrast +
        0.18 * exposed_size +
        propulsion_bias +
        thermal_speed_term
    )

    thermal_score = 100.0 * clamp01(
        thermal_raw *
        altitude_reduction *
        atmosphere_factor *
        gust_uncertainty *
        stealth_reduction
    )

    confidence = 1.0 - (
        0.20 * (cloud_cover / 100.0) +
        0.18 * clamp01(background_complexity) +
        0.10 * (gustiness / 10.0)
    )
    confidence = max(0.45, min(0.95, confidence))

    if power_system == "ICE":
        overall = 0.40 * visual_score + 0.60 * thermal_score
    elif drone_type == "rotor":
        overall = 0.55 * visual_score + 0.45 * thermal_score
    else:
        overall = 0.50 * visual_score + 0.50 * thermal_score

    return {
        'visual_score': round(visual_score, 1),
        'thermal_score': round(thermal_score, 1),
        'overall_score': round(overall, 1),
        'confidence': round(confidence * 100.0, 1),
    }

def render_detectability_alert(visual_score: float, thermal_score: float) -> Tuple[str, str]:
    visual_label, _, visual_bg = _risk_bucket(visual_score)
    thermal_label, _, thermal_bg = _risk_bucket(thermal_score)
    overall_kind = 'error' if 'High' in (visual_label, thermal_label) else ('warning' if 'Moderate' in (visual_label, thermal_label) else 'success')
    badges = "<div style='margin:6px 0;'>" + _badge(f'Visual • {visual_label}', visual_score, visual_bg) + _badge(f'Thermal • {thermal_label}', thermal_score, thermal_bg) + "</div>"
    return overall_kind, badges

UAV_PROFILES = {
    'Generic Quad': {'type': 'rotor', 'power_system': 'Battery', 'base_weight_kg': 1.2, 'max_payload_g': 800, 'battery_wh': 60.0, 'hover_power_W_ref': 150.0, 'parasitic_area_m2': 0.025, 'cd_body': 1.0, 'surface_area_m2': 0.20, 'ai_capabilities': 'Basic flight stabilization, waypoint navigation'},
    'DJI Phantom': {'type': 'rotor', 'power_system': 'Battery', 'base_weight_kg': 1.4, 'max_payload_g': 500, 'battery_wh': 68.0, 'hover_power_W_ref': 140.0, 'parasitic_area_m2': 0.024, 'cd_body': 1.0, 'surface_area_m2': 0.22, 'ai_capabilities': 'Visual object tracking, return-to-home, autonomous mapping'},
    'Skydio 2+': {'type': 'rotor', 'power_system': 'Battery', 'base_weight_kg': 0.8, 'max_payload_g': 150, 'battery_wh': 45.0, 'hover_power_W_ref': 95.0, 'parasitic_area_m2': 0.018, 'cd_body': 1.0, 'surface_area_m2': 0.15, 'ai_capabilities': 'Full obstacle avoidance, visual SLAM, autonomous following'},
    'Freefly Alta 8': {'type': 'rotor', 'power_system': 'Battery', 'base_weight_kg': 6.2, 'max_payload_g': 9000, 'battery_wh': 710.0, 'hover_power_W_ref': 900.0, 'parasitic_area_m2': 0.08, 'cd_body': 1.1, 'surface_area_m2': 0.60, 'ai_capabilities': 'Autonomous camera coordination, precision loitering'},
    'Teal 2 / Golden Eagle': {'type': 'rotor', 'power_system': 'Battery', 'base_weight_kg': 1.25, 'max_payload_g': 300, 'battery_wh': 110.0, 'hover_power_W_ref': 180.0, 'parasitic_area_m2': 0.020, 'cd_body': 1.0, 'surface_area_m2': 0.18, 'ai_capabilities': 'AI-driven ISR, edge-based visual classification, GPS-denied flight'},
    'RQ-11 Raven': {'type': 'fixed', 'power_system': 'Battery', 'base_weight_kg': 1.9, 'max_payload_g': 0, 'battery_wh': 120.0, 'wing_area_m2': 0.24, 'wingspan_m': 1.4, 'cd0': 0.040, 'oswald_e': 0.78, 'prop_eff': 0.72, 'hotel_W': 8.0, 'surface_area_m2': 0.22, 'cl_max': 1.3, 'ai_capabilities': 'Auto-stabilized flight, limited route autonomy'},
    'RQ-20 Puma': {'type': 'fixed', 'power_system': 'Battery', 'base_weight_kg': 6.3, 'max_payload_g': 600, 'battery_wh': 700.0, 'wing_area_m2': 0.55, 'wingspan_m': 2.8, 'cd0': 0.038, 'oswald_e': 0.80, 'prop_eff': 0.75, 'hotel_W': 12.0, 'surface_area_m2': 0.45, 'cl_max': 1.4, 'ai_capabilities': 'AI-enhanced ISR mission planning, autonomous loitering'},
    'Vector AI (Fixed-Wing)': {'type': 'fixed', 'power_system': 'Battery', 'base_weight_kg': 8.0, 'max_payload_g': 1500, 'battery_wh': 1200.0, 'wing_area_m2': 0.90, 'wingspan_m': 2.8, 'cd0': 0.035, 'oswald_e': 0.82, 'prop_eff': 0.78, 'hotel_W': 20.0, 'surface_area_m2': 0.55, 'cl_max': 1.5, 'ai_capabilities': 'Modular AI sensor pods, onboard geospatial intelligence, autonomous route learning'},
    'Vector AI (Multicopter)': {'type': 'rotor', 'power_system': 'Battery', 'base_weight_kg': 8.0, 'max_payload_g': 1500, 'battery_wh': 1200.0, 'hover_power_W_ref': 1200.0, 'parasitic_area_m2': 0.10, 'cd_body': 1.1, 'surface_area_m2': 0.60, 'ai_capabilities': 'VTOL mode for launch/recovery and confined-area operations'},
    'MQ-1 Predator': {'type': 'fixed', 'power_system': 'ICE', 'base_weight_kg': 512.0, 'max_payload_g': 204000, 'battery_wh': 150.0, 'wing_area_m2': 11.5, 'wingspan_m': 16.8, 'cd0': 0.030, 'oswald_e': 0.82, 'prop_eff': 0.80, 'hotel_W': 400.0, 'surface_area_m2': 5.0, 'cl_max': 1.5, 'bsfc_gpkwh': 285.0, 'fuel_density_kgpl': 0.72, 'fuel_tank_l': 379.0, 'ai_capabilities': 'Semi-autonomous surveillance, pattern-of-life analysis'},
    'MQ-9 Reaper': {'type': 'fixed', 'power_system': 'ICE', 'base_weight_kg': 2223.0, 'max_payload_g': 1701000, 'battery_wh': 0.0, 'wing_area_m2': 24.0, 'wingspan_m': 20.1, 'cd0': 0.024, 'oswald_e': 0.88, 'prop_eff': 0.84, 'hotel_W': 700.0, 'surface_area_m2': 8.0, 'cl_max': 1.6, 'bsfc_gpkwh': 255.0, 'fuel_density_kgpl': 0.80, 'fuel_tank_l': 2279.0, 'ai_capabilities': 'Real-time threat detection, sensor fusion, autonomous target tracking'},
    'Custom Build': {'type': 'rotor', 'power_system': 'Battery', 'base_weight_kg': 2.0, 'max_payload_g': 1500, 'battery_wh': 150.0, 'hover_power_W_ref': 220.0, 'parasitic_area_m2': 0.03, 'cd_body': 1.0, 'surface_area_m2': 0.25, 'ai_capabilities': 'User-defined platform with configurable components'},
}

def simulate_battery_aircraft(profile: Dict[str, Any], payload_weight_g: int, flight_speed_kmh: float, wind_speed_kmh: float, temperature_c: float, altitude_m: int, elevation_gain_m: int, flight_mode: str, gustiness: int, terrain_penalty: float, stealth_drag_penalty: float, battery_capacity_wh: float) -> Dict[str, Any]:
    total_mass_kg = profile['base_weight_kg'] + (payload_weight_g / 1000.0)
    weight_N = total_mass_kg * G0
    V_ms = max(1.0, flight_speed_kmh / 3.6)
    W_ms = max(0.0, wind_speed_kmh / 3.6)
    rho, rho_ratio = density_ratio_from_ambient(altitude_m, temperature_c)
    batt_Wh = float(battery_capacity_wh) * battery_temp_capacity_factor(temperature_c)
    climb_Wh = 0.0
    if elevation_gain_m > 0:
        climb_Wh = climb_energy_wh(total_mass_kg, elevation_gain_m, eta_climb=0.75)
        batt_Wh = max(0.0, batt_Wh - climb_Wh)

    if profile['type'] == 'fixed':
        V_eff = V_ms if flight_mode != 'Loiter' else max(8.0, 0.75 * V_ms)
        perf = fixedwing_power_required(weight_N, rho, V_eff, profile['wing_area_m2'], profile['wingspan_m'], profile['cd0'], profile['oswald_e'], profile['prop_eff'], 'Battery', profile.get('hotel_W', HOTEL_W_DEFAULT), 0.10, profile.get('cl_max', 1.4))
        WL = weight_N / max(0.05, profile['wing_area_m2'])
        wind_penalty_frac = mission_gust_penalty_fraction(gustiness, wind_speed_kmh, V_eff, WL)
        total_draw_W = perf['total_W'] * (1.0 + wind_penalty_frac)
        if flight_mode == 'Waypoint Mission':
            total_draw_W *= 1.05
        elif flight_mode == 'Loiter':
            total_draw_W *= 1.05
        total_draw_W *= terrain_penalty * stealth_drag_penalty
        endurance_min = fixedwing_endurance_minutes(batt_Wh, total_draw_W)
        best_km, worst_km = heading_range_km(V_eff, W_ms, endurance_min)
        delta_T = convective_deltaT_simple(total_draw_W, profile.get('surface_area_m2', 0.3), temperature_c, rho, V_eff)
        return {'rho': rho, 'rho_ratio': rho_ratio, 'total_mass_kg': total_mass_kg, 'weight_N': weight_N, 'battery_derated_Wh': batt_Wh, 'climb_energy_Wh': climb_Wh, 'total_draw_W': total_draw_W, 'dispatch_endurance_min': endurance_min, 'best_heading_range_km': best_km, 'upwind_range_km': worst_km, 'thermal_load_deltaT_estimate_C': delta_T, 'wind_penalty_frac': wind_penalty_frac, 'CL': perf['CL'], 'CD': perf['CD'], 'drag_N': perf['drag_N'], 'eta_prop_eff': perf['eta_prop_eff'], 'stall_margin_ok': bool(perf['stall_margin_ok']), 'V_effective_ms': V_eff}

    rotor = rotor_power_required(total_mass_kg, rho_ratio, flight_speed_kmh, profile['hover_power_W_ref'], profile.get('parasitic_area_m2', 0.03), profile.get('cd_body', 1.0), profile.get('hotel_W', HOTEL_W_DEFAULT))
    WL_proxy = max(25.0, weight_N / max(0.15, profile.get('surface_area_m2', 0.25)))
    wind_penalty_frac = mission_gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms, WL_proxy)
    total_draw_W = rotor['total_W'] * (1.0 + wind_penalty_frac)
    if flight_mode == 'Hover':
        total_draw_W *= 1.08
    elif flight_mode == 'Waypoint Mission':
        total_draw_W *= 1.05
    elif flight_mode == 'Loiter':
        total_draw_W *= 1.03
    total_draw_W *= terrain_penalty * stealth_drag_penalty
    endurance_min = fixedwing_endurance_minutes(batt_Wh, total_draw_W)
    best_km, worst_km = heading_range_km(V_ms, W_ms, endurance_min)
    delta_T = convective_deltaT_simple(total_draw_W, profile.get('surface_area_m2', 0.2), temperature_c, rho, V_ms)
    return {'rho': rho, 'rho_ratio': rho_ratio, 'total_mass_kg': total_mass_kg, 'weight_N': weight_N, 'battery_derated_Wh': batt_Wh, 'climb_energy_Wh': climb_Wh, 'total_draw_W': total_draw_W, 'dispatch_endurance_min': endurance_min, 'best_heading_range_km': best_km, 'upwind_range_km': worst_km, 'thermal_load_deltaT_estimate_C': delta_T, 'wind_penalty_frac': wind_penalty_frac, 'induced_W': rotor['induced_W'], 'profile_W': rotor['profile_W'], 'hover_W': rotor['hover_W'], 'parasite_W': rotor['parasite_W'], 'V_effective_ms': V_ms}

def simulate_ice_aircraft(profile: Dict[str, Any], payload_weight_g: int, flight_speed_kmh: float, wind_speed_kmh: float, temperature_c: float, altitude_m: int, elevation_gain_m: int, flight_mode: str, gustiness: int, terrain_penalty: float, stealth_drag_penalty: float, fuel_tank_l: Optional[float] = None) -> Dict[str, Any]:
    total_mass_kg = profile['base_weight_kg'] + (payload_weight_g / 1000.0)
    weight_N = total_mass_kg * G0
    V_ms = max(10.0, flight_speed_kmh / 3.6)
    W_ms = max(0.0, wind_speed_kmh / 3.6)
    rho, rho_ratio = density_ratio_from_ambient(altitude_m, temperature_c)
    V_eff = V_ms if flight_mode != 'Loiter' else max(18.0, 0.80 * V_ms)
    perf = fixedwing_power_required(weight_N, rho, V_eff, profile['wing_area_m2'], profile['wingspan_m'], profile['cd0'], profile['oswald_e'], profile['prop_eff'], 'ICE', profile.get('hotel_W', 250.0), 0.08, profile.get('cl_max', 1.5))
    WL = weight_N / max(0.05, profile['wing_area_m2'])
    wind_penalty_frac = mission_gust_penalty_fraction(gustiness, wind_speed_kmh, V_eff, WL)
    total_power_W = perf['total_W'] * (1.0 + wind_penalty_frac)
    if flight_mode == 'Waypoint Mission':
        total_power_W *= 1.04
    elif flight_mode == 'Loiter':
        total_power_W *= 1.03
    total_power_W *= terrain_penalty * stealth_drag_penalty
    fuel_l_total = float(fuel_tank_l if fuel_tank_l is not None else profile['fuel_tank_l'])
    fuel_l_total = max(0.0, fuel_l_total)
    lph = bsfc_fuel_burn_lph(total_power_W, profile['bsfc_gpkwh'], profile['fuel_density_kgpl'])
    climb_L = climb_fuel_liters(total_mass_kg, max(0, elevation_gain_m), profile['bsfc_gpkwh'], profile['fuel_density_kgpl'], 0.70)
    usable_fuel_L = max(0.0, fuel_l_total * USABLE_FUEL_FRAC - climb_L)
    raw_endurance_hr = usable_fuel_L / max(0.05, lph)
    dispatch_endurance_min = raw_endurance_hr * 60.0 * (1.0 - DISPATCH_RESERVE)
    best_km, worst_km = heading_range_km(V_eff, W_ms, dispatch_endurance_min)
    delta_T = convective_deltaT_simple(total_power_W, profile.get('surface_area_m2', 5.0), temperature_c, rho, V_eff, 0.85)
    return {'rho': rho, 'rho_ratio': rho_ratio, 'total_mass_kg': total_mass_kg, 'weight_N': weight_N, 'total_power_W': total_power_W, 'fuel_burn_L_per_hr': lph, 'climb_fuel_L': climb_L, 'usable_fuel_L': usable_fuel_L, 'dispatch_endurance_min': dispatch_endurance_min, 'best_heading_range_km': best_km, 'upwind_range_km': worst_km, 'thermal_load_deltaT_estimate_C': delta_T, 'wind_penalty_frac': wind_penalty_frac, 'CL': perf['CL'], 'CD': perf['CD'], 'drag_N': perf['drag_N'], 'eta_prop_eff': perf['eta_prop_eff'], 'stall_margin_ok': bool(perf['stall_margin_ok']), 'V_effective_ms': V_eff}

REFERENCE_CASES = [
    {'name': 'RQ-11 Raven', 'target_min': 75.0, 'tolerance_pct': 20.0, 'note': 'Nominal sea-level condition, low wind, no payload'},
    {'name': 'RQ-20 Puma', 'target_min': 180.0, 'tolerance_pct': 20.0, 'note': 'Nominal sea-level condition, low wind, no payload'},
    {'name': 'Teal 2 / Golden Eagle', 'target_min': 30.0, 'tolerance_pct': 20.0, 'note': 'Nominal sea-level condition, low wind, no payload'},
    {'name': 'Vector AI (Fixed-Wing)', 'target_min': 180.0, 'tolerance_pct': 20.0, 'note': 'Fixed-wing mode, nominal sea-level condition'},
    {'name': 'Vector AI (Multicopter)', 'target_min': 45.0, 'tolerance_pct': 20.0, 'note': 'Multicopter mode, nominal sea-level condition'},
    {'name': 'MQ-1 Predator', 'target_min': 1440.0, 'tolerance_pct': 20.0, 'note': 'Nominal sea-level condition, low wind, no payload, cruise near 70 kt'},
    {'name': 'MQ-9 Reaper', 'target_min': 1620.0, 'tolerance_pct': 20.0, 'note': 'Nominal sea-level condition, low wind, no payload, standard fuel'},
]

def pct_error(pred: float, truth: float) -> float:
    if truth == 0:
        return 0.0
    return 100.0 * (pred - truth) / truth

def simulate_nominal_endurance(name: str) -> float:
    p = UAV_PROFILES[name]
    if p['power_system'] == 'Battery':
        out = simulate_battery_aircraft(p, 0, 45.0 if p['type'] == 'fixed' else 20.0, 0.0, 15.0, 0, 0, 'Forward Flight' if p['type'] == 'fixed' else 'Hover', 0, 1.0, 1.0, p['battery_wh'])
        return out['dispatch_endurance_min']
    nominal_speed = 129.6 if name == 'MQ-1 Predator' else 370.0 if name == 'MQ-9 Reaper' else 140.0
    out = simulate_ice_aircraft(p, 0, nominal_speed, 0.0, 15.0, 0, 0, 'Forward Flight', 0, 1.0, 1.0)
    return out['dispatch_endurance_min']

def validation_report() -> List[Dict[str, Any]]:
    rows = []
    for case in REFERENCE_CASES:
        pred = simulate_nominal_endurance(case['name'])
        err = pct_error(pred, case['target_min'])
        rows.append({'platform': case['name'], 'predicted_min': round(pred, 1), 'target_min': case['target_min'], 'error_pct': round(err, 1), 'pass': abs(err) <= case['tolerance_pct'], 'assumption': case['note']})
    return rows

def _responses_text(resp) -> str:
    text = getattr(resp, 'output_text', None)
    if text:
        return text.strip()
    try:
        chunks = []
        for item in getattr(resp, 'output', []):
            for content in getattr(item, 'content', []):
                if getattr(content, 'type', '') == 'output_text':
                    chunks.append(getattr(content, 'text', ''))
        return ''.join(chunks).strip()
    except Exception:
        return ''

def generate_llm_advice(params: Dict[str, Any]) -> str:
    if not OPENAI_AVAILABLE:
        return "LLM unavailable — heuristic advice:\n- Reduce payload for longer endurance.\n- Lower airspeed in gusty winds.\n- Avoid high-drag mission configurations unless required.\n- Preserve reserve margin for ingress and return."
    developer_prompt = 'You are a precise aerospace UAV mission advisor for an educational simulator. Be concise, technically grounded, and operationally practical. Do not invent aircraft or sensor capabilities.'
    user_prompt = f"""Provide 4 short bullet recommendations for this UAV mission.

Parameters:
- Drone: {params['drone']}
- Payload: {params['payload_g']} g
- Mode: {params['mode']}
- Speed: {params['speed_kmh']} km/h
- Altitude: {params['alt_m']} m
- Wind: {params['wind_kmh']} km/h (gust {params['gust']})
- Dispatchable Endurance: {params['endurance_min']:.1f} min
- Thermal Load ΔT Estimate: {params['delta_T']:.1f} °C
- Fuel context: {params['fuel_l']}

Requirements:
- Bullet style only
- Prioritize endurance, control margin, and return safety
- Mention one tradeoff if relevant
"""
    try:
        resp = _client.responses.create(model='gpt-5.4', reasoning={'effort': 'medium'}, input=[{'role': 'developer', 'content': [{'type': 'input_text', 'text': developer_prompt}]}, {'role': 'user', 'content': [{'type': 'input_text', 'text': user_prompt}]}], max_output_tokens=220)
        text = _responses_text(resp)
        if text:
            return text
        raise ValueError('Empty response text')
    except Exception:
        return "LLM error — heuristic advice:\n- Fly closer to best-endurance speed.\n- Reduce drag and payload where possible.\n- Preserve reserve for return-to-base."

ALLOWED_ACTIONS = ['RTB', 'LOITER', 'HANDOFF_TRACK', 'RELOCATE', 'ALTITUDE_CHANGE', 'SPEED_CHANGE', 'RELAY_COMMS', 'STANDBY']

@dataclass
class VehicleState:
    id: str
    role: str
    platform: str
    power_system: str
    x_km: float
    y_km: float
    altitude_m: int
    speed_kmh: float
    endurance_min: float
    battery_wh: float = 0.0
    fuel_l: float = 0.0
    draw_W: float = 0.0
    fuel_burn_lph: float = 0.0
    delta_T: float = 0.0
    current_wp: int = 0
    waypoints: Optional[List[tuple]] = field(default_factory=list)
    status_note: str = ''
    inside_threat_zone: bool = False
    valid_trim: bool = True

def summarize_vehicle_state(s: VehicleState) -> Dict[str, Any]:
    return {'id': s.id, 'role': s.role, 'platform': s.platform, 'power_system': s.power_system, 'x_km': round(s.x_km, 3), 'y_km': round(s.y_km, 3), 'altitude_m': s.altitude_m, 'speed_kmh': round(s.speed_kmh, 2), 'endurance_min': round(s.endurance_min, 2), 'battery_wh': round(s.battery_wh, 2), 'fuel_l': round(s.fuel_l, 3), 'draw_W': round(s.draw_W, 2), 'fuel_burn_lph': round(s.fuel_burn_lph, 3), 'delta_T': round(s.delta_T, 2), 'current_wp': s.current_wp, 'inside_threat_zone': s.inside_threat_zone, 'status_note': s.status_note, 'valid_trim': s.valid_trim}

def in_threat_zone(s: VehicleState, threat_zone_km: float) -> bool:
    return (s.x_km ** 2 + s.y_km ** 2) ** 0.5 <= threat_zone_km

def move_towards_waypoint(s: VehicleState, dt_s: float) -> VehicleState:
    if not s.waypoints or s.current_wp >= len(s.waypoints):
        return s
    tx, ty = s.waypoints[s.current_wp]
    dx = tx - s.x_km
    dy = ty - s.y_km
    dist = math.sqrt(dx * dx + dy * dy)
    if dist <= 1e-6:
        s.current_wp += 1
        return s
    step_km = (max(0.0, s.speed_kmh) * dt_s) / 3600.0
    if step_km >= dist:
        s.x_km = tx
        s.y_km = ty
        s.current_wp += 1
    else:
        s.x_km += step_km * dx / dist
        s.y_km += step_km * dy / dist
    return s

def burn_battery_step(battery_wh: float, draw_W: float, dt_s: float) -> float:
    return max(0.0, battery_wh - (draw_W * dt_s / 3600.0))

def burn_fuel_step(fuel_l: float, fuel_burn_lph: float, dt_s: float) -> float:
    return max(0.0, fuel_l - (fuel_burn_lph * dt_s / 3600.0))

def recompute_endurance_minutes(s: VehicleState) -> float:
    if s.power_system == 'Battery':
        if s.draw_W <= 0:
            return 0.0
        return max(0.0, (s.battery_wh / s.draw_W) * 60.0)
    if s.fuel_burn_lph <= 0:
        return 0.0
    return max(0.0, (s.fuel_l / s.fuel_burn_lph) * 60.0)

def seed_swarm_from_result(platform_name: str, profile: Dict[str, Any], base_result: Dict[str, Any], swarm_size: int, altitude_m: int, waypoints: List[tuple]) -> List[VehicleState]:
    roles = ['LEAD', 'SCOUT', 'TRACKER', 'RELAY', 'STRIKER']
    swarm = []
    for i in range(swarm_size):
        swarm.append(VehicleState(id=f'UAV_{i+1}', role=roles[i % len(roles)], platform=platform_name, power_system=profile['power_system'], x_km=0.0, y_km=0.0, altitude_m=altitude_m, speed_kmh=30.0, endurance_min=float(base_result['dispatch_endurance_min']), battery_wh=float(base_result.get('battery_derated_Wh', 0.0)), fuel_l=float(base_result.get('usable_fuel_L', 0.0)), draw_W=float(base_result.get('total_draw_W', 0.0)), fuel_burn_lph=float(base_result.get('fuel_burn_L_per_hr', 0.0)), delta_T=float(base_result.get('thermal_load_deltaT_estimate_C', 0.0)), current_wp=0, waypoints=waypoints.copy(), valid_trim=bool(base_result.get('stall_margin_ok', True))))
    return swarm

def recompute_vehicle_from_state(s: VehicleState, profile: Dict[str, Any], temperature_c: float, wind_speed_kmh: float, gustiness: int, terrain_penalty: float, stealth_drag_penalty: float) -> VehicleState:
    if s.power_system == 'Battery':
        flight_mode = 'Forward Flight' if profile['type'] == 'fixed' else 'Hover'
        out = simulate_battery_aircraft(profile, 0, s.speed_kmh, wind_speed_kmh, temperature_c, s.altitude_m, 0, flight_mode, gustiness, terrain_penalty, stealth_drag_penalty, s.battery_wh)
        s.draw_W = float(out.get('total_draw_W', s.draw_W))
        s.delta_T = float(out.get('thermal_load_deltaT_estimate_C', s.delta_T))
        s.valid_trim = bool(out.get('stall_margin_ok', True))
        s.endurance_min = float(out.get('dispatch_endurance_min', s.endurance_min))
    else:
        out = simulate_ice_aircraft(profile, 0, s.speed_kmh, wind_speed_kmh, temperature_c, s.altitude_m, 0, 'Forward Flight', gustiness, terrain_penalty, stealth_drag_penalty, s.fuel_l)
        s.fuel_burn_lph = float(out.get('fuel_burn_L_per_hr', s.fuel_burn_lph))
        s.delta_T = float(out.get('thermal_load_deltaT_estimate_C', s.delta_T))
        s.valid_trim = bool(out.get('stall_margin_ok', True))
        s.endurance_min = float(out.get('dispatch_endurance_min', s.endurance_min))
    return s

def _safe_json(txt: str) -> Dict[str, Any]:
    try:
        return json.loads(txt)
    except Exception:
        s = txt.find('{')
        e = txt.rfind('}')
        return json.loads(txt[s:e+1])

AGENT_SYSTEM_TMPL = """You are {role} for {uav_id}, a UAV swarm mission agent.
Return STRICT JSON with:
- "message": short comms (<20 words)
- "proposed_action": one of {allowed}
- "params": dict
- "confidence": float 0-1
Mission rules:
- Prefer RTB if endurance is critically low.
- Prefer LOITER if awaiting tasking.
- Prefer RELAY_COMMS if acting as comms support.
- Use SPEED_CHANGE or ALTITUDE_CHANGE only when tactically justified.
- Do not invent physics. Actions are mission-logic only.
"""

LEAD_SYSTEM = """You are LEAD, the swarm coordinator.
Input: environment + UAV states + proposals.
Return STRICT JSON with:
- "conversation": list of { "from": "...", "msg": "..." }
- "actions": list of { "uav_id": "...", "action": "...", "reason": "...", ...params }
Rules:
- Prioritize survivability and mission continuity.
- RTB if endurance is low.
- Do not invent new action types.
- Use only mission-logic actions, not physics changes.
"""

def agent_call(env: Dict[str, Any], s: VehicleState) -> Dict[str, Any]:
    if not OPENAI_AVAILABLE:
        if s.endurance_min < 8:
            return {'message': 'Low endurance, RTB.', 'proposed_action': 'RTB', 'params': {}, 'confidence': 0.8}
        if s.role == 'RELAY':
            return {'message': 'Holding as relay.', 'proposed_action': 'RELAY_COMMS', 'params': {}, 'confidence': 0.7}
        return {'message': 'Continuing mission.', 'proposed_action': 'LOITER', 'params': {}, 'confidence': 0.6}
    sys = AGENT_SYSTEM_TMPL.format(role=s.role, uav_id=s.id, allowed=ALLOWED_ACTIONS)
    payload = {'env': env, 'self': summarize_vehicle_state(s)}
    try:
        resp = _client.responses.create(model='gpt-5.4', input=[{'role': 'developer', 'content': [{'type': 'input_text', 'text': sys}]}, {'role': 'user', 'content': [{'type': 'input_text', 'text': json.dumps(payload, ensure_ascii=False)}]}], max_output_tokens=180)
        text = _responses_text(resp)
        if text:
            return _safe_json(text)
        raise ValueError('Empty response')
    except Exception:
        return {'message': 'Holding.', 'proposed_action': 'STANDBY', 'params': {}, 'confidence': 0.5}

def lead_call(env: Dict[str, Any], swarm: List[VehicleState], proposals: Dict[str, Any]) -> Dict[str, Any]:
    if not OPENAI_AVAILABLE:
        actions = []
        for s in swarm:
            prop = proposals.get(s.id, {})
            act = prop.get('proposed_action', 'LOITER')
            if s.endurance_min < 8:
                actions.append({'uav_id': s.id, 'action': 'RTB', 'reason': 'Low endurance'})
            elif act == 'RELAY_COMMS':
                actions.append({'uav_id': s.id, 'action': 'RELAY_COMMS', 'reason': 'Relay support'})
            elif act == 'ALTITUDE_CHANGE':
                actions.append({'uav_id': s.id, 'action': 'ALTITUDE_CHANGE', 'delta_m': 50, 'reason': 'Altitude adjust'})
            elif act == 'SPEED_CHANGE':
                actions.append({'uav_id': s.id, 'action': 'SPEED_CHANGE', 'delta_kmh': -5, 'reason': 'Conserve energy'})
            else:
                actions.append({'uav_id': s.id, 'action': 'LOITER', 'reason': 'Hold position'})
        return {'conversation': [{'from': 'LEAD', 'msg': 'Fallback coordination active'}], 'actions': actions}
    packed = {'env': env, 'swarm': [summarize_vehicle_state(s) for s in swarm], 'proposals': proposals, 'allowed_actions': ALLOWED_ACTIONS}
    try:
        resp = _client.responses.create(model='gpt-5.4', input=[{'role': 'developer', 'content': [{'type': 'input_text', 'text': LEAD_SYSTEM}]}, {'role': 'user', 'content': [{'type': 'input_text', 'text': json.dumps(packed, ensure_ascii=False)}]}], max_output_tokens=500)
        text = _responses_text(resp)
        if text:
            return _safe_json(text)
        raise ValueError('Empty response')
    except Exception:
        return {'conversation': [{'from': 'LEAD', 'msg': 'LLM fallback active'}], 'actions': [{'uav_id': s.id, 'action': 'LOITER', 'reason': 'Fallback hold'} for s in swarm]}

def apply_swarm_actions(swarm: List[VehicleState], actions: List[Dict[str, Any]], threat_zone_km: float, profile: Dict[str, Any], temperature_c: float, wind_speed_kmh: float, gustiness: int, terrain_penalty: float, stealth_drag_penalty: float) -> List[VehicleState]:
    idx = {s.id: s for s in swarm}
    for a in actions:
        s = idx.get(a.get('uav_id'))
        if not s:
            continue
        act = a.get('action', 'STANDBY')
        if act == 'RTB':
            s.status_note = 'RTB ordered'
            s.waypoints = [(0.0, 0.0)]
            s.current_wp = 0
        elif act == 'LOITER':
            s.status_note = 'Loiter'
            s.speed_kmh = max(10.0, s.speed_kmh * 0.90)
        elif act == 'HANDOFF_TRACK':
            s.status_note = 'Track handoff'
        elif act == 'RELOCATE':
            dx = float(a.get('dx_km', 0.0))
            dy = float(a.get('dy_km', 0.0))
            s.x_km += dx
            s.y_km += dy
            s.status_note = f'Relocate ({dx:+.1f},{dy:+.1f}) km'
        elif act == 'ALTITUDE_CHANGE':
            delta_m = int(a.get('delta_m', 0))
            s.altitude_m = max(0, s.altitude_m + delta_m)
            s.status_note = f'Altitude change {delta_m:+d} m'
        elif act == 'SPEED_CHANGE':
            delta_kmh = float(a.get('delta_kmh', 0.0))
            s.speed_kmh = max(5.0, s.speed_kmh + delta_kmh)
            s.status_note = f'Speed change {delta_kmh:+.1f} km/h'
        elif act == 'RELAY_COMMS':
            s.status_note = 'Relay node active'
        else:
            s.status_note = 'Standby'
        s.inside_threat_zone = in_threat_zone(s, threat_zone_km)
        s = recompute_vehicle_from_state(s, profile, temperature_c, wind_speed_kmh, gustiness, terrain_penalty, stealth_drag_penalty)
    return swarm

def simulate_swarm_step(swarm: List[VehicleState], dt_s: float, threat_zone_km: float) -> List[VehicleState]:
    updated = []
    for s in swarm:
        s = move_towards_waypoint(s, dt_s)
        s.inside_threat_zone = in_threat_zone(s, threat_zone_km)
        if s.power_system == 'Battery':
            s.battery_wh = burn_battery_step(s.battery_wh, s.draw_W, dt_s)
        else:
            s.fuel_l = burn_fuel_step(s.fuel_l, s.fuel_burn_lph, dt_s)
        s.endurance_min = recompute_endurance_minutes(s)
        updated.append(s)
    return updated

def plot_swarm_map(swarm: List[VehicleState], threat_zone_km: float, show_threat_zone: bool, waypoints: Optional[List[tuple]] = None):
    fig, ax = make_themed_figure(figsize=(5, 5))

    if show_threat_zone:
        circle = plt.Circle((0, 0), threat_zone_km, color=ACTIVE_THEME["danger"], alpha=0.16, label="Threat Zone")
        ax.add_patch(circle)

    if waypoints:
        xs, ys = zip(*waypoints)
        ax.plot(xs, ys, linestyle="--", linewidth=1.4, color=ACTIVE_THEME["path"], label="Mission Path")
        ax.scatter(xs, ys, color=ACTIVE_THEME["warning"], marker="x", s=80, label="Waypoints")

    for s in swarm:
        marker = "o" if s.power_system == "Battery" else "s"
        if s.inside_threat_zone:
            color = ACTIVE_THEME["danger"]
        elif s.power_system == "ICE":
            color = ACTIVE_THEME["accent2"]
        else:
            color = ACTIVE_THEME["accent"]

        ax.scatter(s.x_km, s.y_km, marker=marker, s=110, color=color, edgecolors=ACTIVE_THEME["panel"], linewidths=0.7, zorder=3)
        ax.text(
            s.x_km + 0.08,
            s.y_km + 0.08,
            f"{s.id}\n{s.role}\nEnd {s.endurance_min:.1f}m",
            fontsize=7,
            color=ACTIVE_THEME["text"],
            bbox=dict(boxstyle="round,pad=0.22", facecolor=ACTIVE_THEME["panel"], edgecolor=ACTIVE_THEME["grid"], alpha=0.92),
        )

    ax.set_title("Swarm Mission Map")
    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.axhline(0, color=ACTIVE_THEME["grid"], linewidth=0.8)
    ax.axvline(0, color=ACTIVE_THEME["grid"], linewidth=0.8)
    ax.set_aspect("equal", adjustable="datalim")
    style_axes(ax)

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        legend = ax.legend(handles, labels, facecolor=ACTIVE_THEME["panel"], edgecolor=ACTIVE_THEME["grid"], fontsize=8, loc="upper right")
        for txt in legend.get_texts():
            txt.set_color(ACTIVE_THEME["text"])

    return fig


st.sidebar.header('Control Panel')
st.sidebar.caption('Global settings for UI, panels, simulation, and layout.')

debug_mode = st.sidebar.toggle('Enable Debug Mode', value=False)
allow_pack_override = st.sidebar.toggle('Allow Battery Override (debug)', value=False) if debug_mode else False

system_mode = st.sidebar.radio(
    'System Mode',
    ['Engineering Mode', 'Swarm / Mission Ops Mode'],
    index=0,
)

show_advanced = st.sidebar.toggle('Show Advanced Metrics', value=True)
show_validation = st.sidebar.toggle('Show Validation Panel', value=True)
show_detectability = st.sidebar.toggle('Show Detectability Panel', value=True)
show_live_simulation = st.sidebar.toggle('Enable Live Simulation', value=True)
show_json_preview = st.sidebar.toggle('Show JSON Export Preview', value=True)
compact_layout = st.sidebar.toggle('Compact Layout', value=False)

drone_model = st.selectbox('Drone Model', list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]
st.info(f"**AI Capabilities:** {profile.get('ai_capabilities', '—')}")
st.caption(f"Base weight: {profile['base_weight_kg']} kg — Max payload: {profile['max_payload_g']} g")
st.caption(f"Power system: `{profile['power_system']}` | Type: `{profile['type']}`")

initial_caution = "Nominal"
initial_caution_class = "status-ok"
if profile['power_system'] == 'ICE':
    initial_caution = "Higher thermal load"
    initial_caution_class = "status-warn"
if profile['type'] == 'rotor':
    initial_caution = "Hover-heavy mission"
    initial_caution_class = "status-warn"

st.markdown(
    render_status_strip(
        platform_type=profile['type'],
        power_system=profile['power_system'],
        theme_name=theme_mode,
        caution_label=initial_caution,
        caution_class=initial_caution_class,
    ),
    unsafe_allow_html=True,
)

flight_mode_options = ['Forward Flight', 'Loiter', 'Waypoint Mission'] if profile['type'] == 'fixed' else ['Hover', 'Forward Flight', 'Loiter', 'Waypoint Mission']

with st.form('uav_form'):
    left, right = st.columns(2)
    with left:
        st.subheader('Flight Parameters')
        battery_capacity_wh = numeric_input('Battery Capacity (Wh)', float(profile.get('battery_wh', 100.0)))
        default_payload = min(max(0, int(profile['max_payload_g'] * 0.5)), profile['max_payload_g'])
        payload_weight_g = int(numeric_input('Payload (g)', default_payload))
        flight_speed_kmh = numeric_input('Speed (km/h)', 30.0)
        wind_speed_kmh = numeric_input('Wind (km/h)', 10.0)
        temperature_c = numeric_input('Temperature (°C)', 25.0)
        altitude_m = int(numeric_input('Altitude (m)', 0))
        elevation_gain_m = int(numeric_input('Elevation Gain (m)', 0))
        flight_mode = st.selectbox('Flight Mode', flight_mode_options)
    with right:
        st.subheader('Mission / Environment')
        cloud_cover = st.slider('Cloud Cover (%)', 0, 100, 50)
        gustiness = st.slider('Gust Factor', 0, 10, 2)
        terrain_penalty = st.slider('Terrain Complexity', 1.0, 1.5, 1.1)
        stealth_drag_penalty = st.slider('Stealth Drag Factor', 1.0, 1.5, 1.0)
        effective_size_default = float(DEFAULT_SIZE_M.get(drone_model, 1.0))
        effective_size_m = st.slider('Effective Visual Size (m)', 0.2, 20.0, min(20.0, effective_size_default))
        background_complexity = st.slider('Background Complexity', 0.0, 1.0, 0.5)
        humidity_factor = st.slider('Humidity / Haze Factor', 0.0, 1.0, 0.5)
        fuel_tank_l = None
        if profile['power_system'] == 'ICE':
            st.markdown('### ICE Configuration')
            fuel_tank_l = numeric_input('Fuel Tank (L)', float(profile.get('fuel_tank_l', 300.0)))
    st.markdown('### Mission Waypoints')
    waypoint_str = st.text_area('Waypoints (e.g., 2,2; 5,0; 8,-3)', '2,2; 5,0; 8,-3')
    submitted = st.form_submit_button('Estimate')

waypoints = []
try:
    for pair in waypoint_str.split(';'):
        x_str, y_str = pair.split(',')
        waypoints.append((float(x_str.strip()), float(y_str.strip())))
except Exception:
    st.error('Invalid waypoint format. Using default waypoint at origin.')
    waypoints = [(0.0, 0.0)]

if submitted:
    try:
        if payload_weight_g > profile['max_payload_g']:
            st.error('Payload exceeds lift capacity.')
            st.stop()

        if profile['power_system'] == 'Battery':
            battery_capacity_wh = clamp_battery(profile, battery_capacity_wh, allow_pack_override)
            result = simulate_battery_aircraft(profile, payload_weight_g, flight_speed_kmh, wind_speed_kmh, temperature_c, altitude_m, elevation_gain_m, flight_mode, gustiness, terrain_penalty, stealth_drag_penalty, battery_capacity_wh)
        else:
            result = simulate_ice_aircraft(profile, payload_weight_g, flight_speed_kmh, wind_speed_kmh, temperature_c, altitude_m, elevation_gain_m, flight_mode, gustiness, terrain_penalty, stealth_drag_penalty, fuel_tank_l)

        rho = result['rho']
        rho_ratio = result['rho_ratio']
        total_weight_kg = result['total_mass_kg']
        weight_N = result['weight_N']
        flight_time_minutes = result['dispatch_endurance_min']
        best_km = result['best_heading_range_km']
        worst_km = result['upwind_range_km']
        delta_T = result['thermal_load_deltaT_estimate_C']
        wind_penalty_frac = result['wind_penalty_frac']
        wind_penalty_pct = wind_penalty_frac * 100.0
        V_ms = max(1.0, flight_speed_kmh / 3.6)
        W_ms = max(0.0, wind_speed_kmh / 3.6)
        effective_speed_kmh = result.get('V_effective_ms', V_ms) * 3.6
        total_distance_km = (effective_speed_kmh * flight_time_minutes) / 60.0

        st.markdown("<div class='section-card'><div class='section-title'>Atmospheric Conditions</div><div class='section-note'>Ambient density and standard-atmosphere context for the selected mission.</div></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.metric('Air Density ρ', f'{rho:.3f} kg/m³')
        with c2:
            st.metric('Density Ratio ρ/ρ₀', f'{rho_ratio:.3f}')

        st.markdown("<div class='section-card'><div class='section-title'>Applied Environment Factors</div><div class='section-note'>How air density, gust loading, terrain complexity, and drag penalties are influencing the estimate.</div></div>", unsafe_allow_html=True)
        if profile['type'] == 'rotor':
            st.markdown(f"**Rotorcraft Air Density Scaling:** `1/sqrt(ρ/ρ₀)` applied to the rotor power estimate.  \nCurrent density ratio ρ/ρ₀ = `{rho_ratio:.3f}`")
        else:
            st.markdown(f"**Fixed-Wing Air Density Effect:** applied through dynamic pressure and required lift.  \nCurrent density ratio ρ/ρ₀ = `{rho_ratio:.3f}`")

        detect = compute_detectability_scores_v3(delta_T, altitude_m, flight_speed_kmh, cloud_cover, gustiness, stealth_drag_penalty, profile['type'], profile['power_system'], effective_size_m, background_complexity, humidity_factor)
        visual_score = detect['visual_score']
        thermal_score = detect['thermal_score']
        overall_score = detect['overall_score']
        detect_confidence = detect['confidence']
        overall_kind, badges_html = render_detectability_alert(visual_score, thermal_score)

        if show_detectability:
            st.subheader('AI/IR Detectability Alert')
            st.caption('AI visual and IR thermal detectability scores are heuristic mission-awareness estimates.')
            if overall_score < 33:
                st.success('Overall detectability: LOW')
            elif overall_score < 67:
                st.warning('Overall detectability: MODERATE')
            else:
                st.error('Overall detectability: HIGH')
            st.markdown(badges_html, unsafe_allow_html=True)
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.metric('Visual Detectability', f'{visual_score:.0f}/100')
            with d2:
                st.metric('IR Thermal Detectability', f'{thermal_score:.0f}/100')
            with d3:
                st.metric('Overall Detectability', f'{overall_score:.0f}/100')
            with d4:
                st.metric('Heuristic Confidence', f'{detect_confidence:.0f}/100')

        caution_label = 'Nominal Conditions'
        caution_class = 'status-ok'
        if overall_score >= 33 or wind_penalty_pct >= 10 or gustiness >= 5:
            caution_label = 'Elevated Risk'
            caution_class = 'status-warn'
        if overall_score >= 67 or (profile['type'] == 'fixed' and not result.get('stall_margin_ok', True)):
            caution_label = 'High Risk'
            caution_class = 'status-danger'

        st.markdown(
            render_status_strip(
                platform_type=profile['type'],
                power_system=profile['power_system'],
                theme_name=theme_mode,
                caution_label=caution_label,
                caution_class=caution_class,
            ),
            unsafe_allow_html=True,
        )

        if profile['type'] == 'fixed' and not result.get('stall_margin_ok', True):
            st.error('Selected speed / weight / altitude combination exceeds configured CL_max. Result is outside valid fixed-wing trim assumptions.')

        if profile['power_system'] == 'Battery':
            st.markdown("<div class='section-card'><div class='section-title'>Thermal Signature Risk & Battery</div><div class='section-note'>Thermal burden and electrical power demand for the current mission estimate.</div></div>", unsafe_allow_html=True)
            risk = 'Low' if delta_T < 10 else ('Moderate' if delta_T < 20 else 'High')
            b1, b2, b3 = st.columns(3)
            with b1:
                st.metric('Thermal Signature Risk', f"{risk} (ΔT = {delta_T:.1f}°C)")
            with b2:
                st.metric('Total Draw (incl. hotel/penalties)', f"{result['total_draw_W']:.0f} W")
            with b3:
                st.metric('Battery Capacity (derated)', f"{result['battery_derated_Wh']:.1f} Wh")
            if show_advanced:
                if profile['type'] == 'fixed':
                    d1, d2, d3, d4 = st.columns(4)
                    with d1:
                        st.metric('CL', f"{result['CL']:.3f}")
                    with d2:
                        st.metric('CD', f"{result['CD']:.4f}")
                    with d3:
                        st.metric('Drag', f"{result['drag_N']:.2f} N")
                    with d4:
                        st.metric('Prop η', f"{result['eta_prop_eff']:.2f}")
                else:
                    d1, d2, d3, d4 = st.columns(4)
                    with d1:
                        st.metric('Induced Power', f"{result['induced_W']:.0f} W")
                    with d2:
                        st.metric('Profile Power', f"{result['profile_W']:.0f} W")
                    with d3:
                        st.metric('Parasite Power', f"{result['parasite_W']:.0f} W")
                    with d4:
                        st.metric('Hover Ref Power', f"{result['hover_W']:.0f} W")
        else:
            st.markdown("<div class='section-card'><div class='section-title'>Fuel, Power & Thermal</div><div class='section-note'>Fuel consumption, power demand, and thermal burden for the current mission estimate.</div></div>", unsafe_allow_html=True)
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                st.metric('Total Shaft+Hotel Power', f"{result['total_power_W'] / 1000.0:.2f} kW")
            with f2:
                st.metric('Fuel Burn', f"{result['fuel_burn_L_per_hr']:.2f} L/hr")
            with f3:
                st.metric('Usable Fuel After Reserve', f"{result['usable_fuel_L']:.2f} L")
            with f4:
                st.metric('Thermal Load ΔT Estimate', f'{delta_T:.1f} °C')
            if show_advanced:
                d1, d2, d3, d4 = st.columns(4)
                with d1:
                    st.metric('CL', f"{result['CL']:.3f}")
                with d2:
                    st.metric('CD', f"{result['CD']:.4f}")
                with d3:
                    st.metric('Drag', f"{result['drag_N']:.2f} N")
                with d4:
                    st.metric('Prop η', f"{result['eta_prop_eff']:.2f}")

        lo = flight_time_minutes * 0.90
        hi = flight_time_minutes * 1.10
        st.markdown("<div class='section-card'><div class='section-title'>Selected UAV — Mission Performance</div><div class='section-note'>Primary mission metrics from the current run.</div></div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric('Dispatchable Endurance', f'{flight_time_minutes:.1f} minutes')
        with m2:
            st.metric('Total Distance', f'{total_distance_km:.1f} km')
        with m3:
            st.metric('Best Heading Range', f'{best_km:.1f} km')
        with m4:
            st.metric('Upwind Range', f'{worst_km:.1f} km')
        st.caption(f'Uncertainty band: {lo:.1f}–{hi:.1f} min (±10%)')

        detail = {'drone_model': drone_model, 'type': profile['type'], 'power_system': profile['power_system'], 'payload_g': payload_weight_g, 'total_mass_kg': round(total_weight_kg, 3), 'weight_N': round(weight_N, 2), 'flight_speed_kmh': round(flight_speed_kmh, 2), 'effective_speed_ms': round(result.get('V_effective_ms', V_ms), 3), 'wind_speed_kmh': round(wind_speed_kmh, 2), 'wind_speed_ms': round(W_ms, 3), 'altitude_m': altitude_m, 'temperature_C': temperature_c, 'flight_mode': flight_mode, 'rho': round(rho, 4), 'rho_ratio': round(rho_ratio, 4), 'gustiness': gustiness, 'terrain_factor': round(terrain_penalty, 3), 'stealth_drag_factor': round(stealth_drag_penalty, 3), 'wind_penalty_pct': round(wind_penalty_pct, 2), 'thermal_load_deltaT_estimate_C': round(delta_T, 2), 'dispatch_endurance_min': round(flight_time_minutes, 2), 'total_distance_km': round(total_distance_km, 2), 'best_heading_range_km': round(best_km, 2), 'upwind_range_km': round(worst_km, 2), 'visual_heuristic_score_0_100': round(visual_score, 1), 'thermal_heuristic_score_0_100': round(thermal_score, 1), 'blended_detectability_score_0_100': round(overall_score, 1), 'heuristic_confidence_0_100': round(detect_confidence, 1), 'detectability_overall': 'LOW' if overall_kind == 'success' else 'MODERATE' if overall_kind == 'warning' else 'HIGH'}

        if profile['power_system'] == 'Battery':
            detail.update({'battery_derated_Wh': round(result['battery_derated_Wh'], 2), 'climb_energy_Wh': round(result['climb_energy_Wh'], 2), 'total_draw_W': round(result['total_draw_W'], 2)})
            if profile['type'] == 'fixed':
                detail.update({'CL': round(result['CL'], 4), 'CD': round(result['CD'], 5), 'drag_N': round(result['drag_N'], 3), 'eta_prop_eff': round(result['eta_prop_eff'], 3), 'stall_margin_ok': bool(result['stall_margin_ok'])})
            else:
                detail.update({'induced_W': round(result['induced_W'], 2), 'profile_W': round(result['profile_W'], 2), 'hover_W': round(result['hover_W'], 2), 'parasite_W': round(result['parasite_W'], 2)})
        else:
            detail.update({'total_power_W': round(result['total_power_W'], 2), 'fuel_burn_L_per_hr': round(result['fuel_burn_L_per_hr'], 3), 'climb_fuel_L': round(result['climb_fuel_L'], 3), 'usable_fuel_L': round(result['usable_fuel_L'], 3), 'CL': round(result['CL'], 4), 'CD': round(result['CD'], 5), 'drag_N': round(result['drag_N'], 3), 'eta_prop_eff': round(result['eta_prop_eff'], 3), 'stall_margin_ok': bool(result['stall_margin_ok'])})

        st.markdown("<div class='section-card'><div class='section-title'>Individual UAV Detailed Results</div><div class='section-note'>Machine-readable and human-readable breakdown for the selected platform.</div></div>", unsafe_allow_html=True)
        human = [
            f"- **Model**: {drone_model} ({profile['type']}, {profile['power_system']})",
            f"- **Payload used**: {payload_weight_g} g (max {profile['max_payload_g']} g)",
            f"- **Mass**: {total_weight_kg:.3f} kg",
            f"- **Weight**: {weight_N:.2f} N",
            f"- **Atmosphere**: ρ={rho:.3f} kg/m³, ρ/ρ₀={rho_ratio:.3f}, T={temperature_c:.1f}°C, Alt={altitude_m} m",
            f"- **Speed**: {flight_speed_kmh:.1f} km/h ({V_ms:.2f} m/s)",
            f"- **Wind**: {wind_speed_kmh:.1f} km/h ({W_ms:.2f} m/s)",
            f"- **Wind penalty**: {wind_penalty_pct:.1f}%",
            f"- **Terrain × stealth factor**: {(terrain_penalty * stealth_drag_penalty):.3f}",
            f"- **Thermal Signature Risk**: {'Low' if delta_T < 10 else 'Moderate' if delta_T < 20 else 'High'} (ΔT = {delta_T:.1f} °C)",
            f"- **Dispatchable endurance**: {flight_time_minutes:.1f} min",
            f"- **Total distance**: {total_distance_km:.2f} km",
            f"- **Best heading / Upwind ranges**: {best_km:.2f} km / {worst_km:.2f} km",
            f"- **Detectability heuristic (Visual / Thermal / Blended)**: {visual_score:.0f}/100 / {thermal_score:.0f}/100 / {overall_score:.0f}/100",
            f"- **Heuristic confidence**: {detect_confidence:.0f}/100",
        ]
        if compact_layout:
            st.markdown('\n'.join(human[:10]))
        else:
            st.markdown('\n'.join(human))
        if not compact_layout:
            st.json(detail, expanded=False)

        indiv_df = pd.DataFrame([detail])
        safe_name = drone_model.replace(' ', '_').replace('/', '_').lower()
        st.download_button('⬇️ Download Individual UAV Detailed Results (CSV)', data=indiv_df.to_csv(index=False).encode('utf-8'), file_name=f'{safe_name}_detailed_results.csv', mime='text/csv')
        st.download_button('⬇️ Download Individual UAV Detailed Results (JSON)', data=json.dumps(detail, indent=2), file_name=f'{safe_name}_detailed_results.json', mime='application/json')

        st.subheader('AI Mission Advisor (LLM)')
        params = {'drone': drone_model, 'payload_g': payload_weight_g, 'mode': flight_mode, 'speed_kmh': flight_speed_kmh, 'alt_m': altitude_m, 'wind_kmh': wind_speed_kmh, 'gust': gustiness, 'endurance_min': flight_time_minutes, 'delta_T': delta_T, 'fuel_l': result.get('usable_fuel_L', 0.0)}
        st.write(generate_llm_advice(params))

        if show_validation:
            st.subheader('Model Validation')
            st.caption('Nominal-condition comparison against reference endurance targets.')
            st.dataframe(pd.DataFrame(validation_report()), use_container_width=True)

        st.subheader('Export Scenario Summary')
        results_summary = {'Drone Model': drone_model, 'Power System': profile['power_system'], 'Type': profile['type'], 'Flight Mode': flight_mode, 'Payload (g)': int(payload_weight_g), 'Speed (km/h)': float(flight_speed_kmh), 'Wind (km/h)': float(wind_speed_kmh), 'Gustiness (0-10)': int(gustiness), 'Altitude (m)': int(altitude_m), 'Temperature (C)': float(temperature_c), 'Air Density (kg/m^3)': round(rho, 3), 'Density Ratio (rho/rho0)': round(rho_ratio, 3), 'Wind Penalty (%)': round(wind_penalty_pct, 2), 'Dispatchable Endurance (min)': round(flight_time_minutes, 2), 'Total Distance (km)': round(total_distance_km, 2), 'Best Heading Range (km)': round(best_km, 2), 'Upwind Range (km)': round(worst_km, 2), 'Thermal Signature Risk': ('Low' if delta_T < 10 else 'Moderate' if delta_T < 20 else 'High'),
            'ΔT (C)': round(delta_T, 2), 'Visual Heuristic Score (0-100)': round(visual_score, 1), 'Thermal Heuristic Score (0-100)': round(thermal_score, 1), 'Blended Detectability Score (0-100)': round(overall_score, 1), 'Heuristic Confidence (0-100)': round(detect_confidence, 1), 'Overall Detectability': detail['detectability_overall']}
        if profile['power_system'] == 'Battery':
            results_summary['Battery Capacity (Wh)'] = round(result['battery_derated_Wh'], 2)
            results_summary['Total Draw (W)'] = round(result['total_draw_W'], 2)
            results_summary['Climb Energy (Wh)'] = round(result['climb_energy_Wh'], 2)
        else:
            results_summary['Fuel Burn (L/hr)'] = round(result['fuel_burn_L_per_hr'], 3)
            results_summary['Climb Fuel (L)'] = round(result['climb_fuel_L'], 3)
            results_summary['Usable Fuel (L)'] = round(result['usable_fuel_L'], 3)
            results_summary['Total Power (W)'] = round(result['total_power_W'], 2)
        df_res = pd.DataFrame([results_summary])
        csv_buffer = io.BytesIO()
        df_res.to_csv(csv_buffer, index=False)
        st.download_button('⬇️ Download Scenario Summary (CSV)', data=csv_buffer, file_name='mission_results.csv', mime='text/csv')
        json_str = json.dumps(results_summary, indent=2)
        st.download_button('⬇️ Download Scenario Summary (JSON)', data=json_str, file_name='mission_results.json', mime='application/json')
        if show_json_preview:
            st.text_area('Scenario Summary (JSON Copy-Paste)', json_str, height=250)

        st.subheader('Mission Energy Profile')
        st.caption('Quick-look depletion profile for the current scenario.')

        fig_energy, ax_energy = make_themed_figure(figsize=(6, 3))
        duration_min_axis = [0.0, max(flight_time_minutes, 0.01)]
        if profile['power_system'] == 'Battery':
            start_store = float(result['battery_derated_Wh'])
            y_vals = [start_store, 0.0]
            ax_energy.plot(duration_min_axis, y_vals, linewidth=2.4, color=ACTIVE_THEME['accent'])
            ax_energy.fill_between(duration_min_axis, y_vals, color=ACTIVE_THEME['accent'], alpha=0.18)
            ax_energy.set_ylabel('Battery (Wh)')
            ax_energy.set_title('Battery Depletion Profile')
        else:
            start_store = float(result['usable_fuel_L'])
            y_vals = [start_store, 0.0]
            ax_energy.plot(duration_min_axis, y_vals, linewidth=2.4, color=ACTIVE_THEME['accent2'])
            ax_energy.fill_between(duration_min_axis, y_vals, color=ACTIVE_THEME['accent2'], alpha=0.18)
            ax_energy.set_ylabel('Fuel (L)')
            ax_energy.set_title('Fuel Depletion Profile')
        ax_energy.set_xlabel('Mission Time (min)')
        style_axes(ax_energy)
        st.pyplot(fig_energy)
        plt.close(fig_energy)

        st.subheader('AI Suggestions (Heuristics)')
        if payload_weight_g == profile['max_payload_g']:
            st.write('**Tip:** Payload is at maximum lift capacity.')
        if wind_speed_kmh > 15:
            st.write('**Tip:** High wind may reduce endurance and especially upwind range.')
        if profile['power_system'] == 'Battery' and result.get('battery_derated_Wh', 9999) < 30:
            st.write('**Tip:** Battery is under 30 Wh after derating. Consider a larger pack.')
        if flight_mode in ['Hover', 'Waypoint Mission', 'Loiter']:
            st.write('**Tip:** Maneuvering or station-keeping increases mission energy demand.')
        if stealth_drag_penalty > 1.2:
            st.write('**Tip:** Stealth loadout penalty is materially reducing endurance.')
        if delta_T > 15:
            st.write('**Tip:** Thermal load estimate is high. Reduce payload, airspeed, or hotel load if possible.')
        if altitude_m > 100:
            st.write('**Tip:** Higher altitude changes observability tradeoffs and may reduce control margin for some platforms.')
        if gustiness >= 5:
            st.write('**Tip:** Gust factor above 5 can seriously degrade small-UAV performance margins.')
        if profile['type'] == 'fixed' and not result.get('stall_margin_ok', True):
            st.write('**Tip:** Increase speed, reduce payload, or descend to restore valid lift margin.')

        if show_live_simulation:
            st.subheader('Live Simulation')
            time_step = 10
            total_steps = min(max(1, int(flight_time_minutes * 60 / time_step)), 240)
            progress = st.progress(0)
            status = st.empty()
            gauge = st.empty()
            timer = st.empty()

            if profile['power_system'] == 'Battery':
                start_wh = result['battery_derated_Wh']
                burn_per_step = (result['total_draw_W'] * time_step) / 3600.0
                for step in range(total_steps + 1):
                    elapsed = step * time_step
                    rem_wh = max(0.0, start_wh - step * burn_per_step)
                    pct = 0.0 if start_wh <= 0 else 100.0 * rem_wh / start_wh
                    bars = int(pct // 10)
                    gauge.markdown(f"**Battery Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {pct:.0f}%`")
                    remain = max(0, int(flight_time_minutes * 60 - elapsed))
                    timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** {remain} sec")
                    status.markdown(
                        f"**Battery Remaining:** {rem_wh:.2f} Wh  "
                        f"**Power Draw:** {result['total_draw_W']:.0f} W  "
                        f"**V:** {effective_speed_kmh:.0f} km/h"
                    )
                    progress.progress(min(step / total_steps, 1.0))
                    if rem_wh <= 0:
                        break
                    time.sleep(0.02)
            else:
                start_fuel = result['usable_fuel_L']
                fuel_per_sec = result['fuel_burn_L_per_hr'] / 3600.0
                for step in range(total_steps + 1):
                    elapsed = step * time_step
                    rem_L = max(0.0, start_fuel - fuel_per_sec * elapsed)
                    pct = 0.0 if start_fuel <= 0 else 100.0 * rem_L / start_fuel
                    bars = int(pct // 10)
                    gauge.markdown(f"**Fuel Gauge:** `[{'|' * bars}{' ' * (10 - bars)}] {pct:.0f}%`")
                    remain = max(0, int(flight_time_minutes * 60 - elapsed))
                    timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** {remain} sec")
                    status.markdown(
                        f"**Fuel Remaining:** {rem_L:.2f} L  "
                        f"**Burn:** {result['fuel_burn_L_per_hr']:.2f} L/hr  "
                        f"**V:** {effective_speed_kmh:.0f} km/h"
                    )
                    progress.progress(min(step / total_steps, 1.0))
                    if rem_L <= 0:
                        break
                    time.sleep(0.02)

        if system_mode == 'Swarm / Mission Ops Mode':
            st.header('Swarm / Mission Ops Module')
            st.caption('Conceptual coordination layer for mission logic, delegation, and playback. This module is not part of the validated aircraft performance model.')
            swarm_enable = st.checkbox('Enable Swarm Module', value=True)
            swarm_size = st.slider('Swarm Size', 2, 8, 3)
            swarm_steps = st.slider('Swarm Coordination Rounds', 1, 5, 2)
            threat_zone_km = st.slider('Threat Zone Radius (km)', 1.0, 20.0, 5.0)
            playback_minutes = st.slider('Playback Length (minutes)', 1, 20, 10)
            if swarm_enable:
                swarm = seed_swarm_from_result(drone_model, profile, result, swarm_size, altitude_m, waypoints)

                st.write('**Initial Swarm State**')
                for s in swarm:
                    st.write(
                        f"- {s.id} [{s.role}] — End {s.endurance_min:.1f} min | "
                        f"Batt {s.battery_wh:.1f} Wh | Fuel {s.fuel_l:.2f} L | "
                        f"Alt {s.altitude_m} m | Pos ({s.x_km:+.1f},{s.y_km:+.1f}) km"
                    )

                env = {'mission': flight_mode, 'wind_kmh': wind_speed_kmh, 'gust': gustiness, 'threat_zone_km': threat_zone_km, 'thermal_context': round(delta_T, 2), 'platform': drone_model}
                for round_idx in range(swarm_steps):
                    st.subheader(f'Coordination Round {round_idx + 1}')
                    proposals = {s.id: agent_call(env, s) for s in swarm}
                    fused = lead_call(env, swarm, proposals)

                    if fused.get('conversation'):
                        st.markdown('**Swarm Conversation**')
                        for m in fused['conversation']:
                            st.write(f"**{m.get('from', 'LEAD')}:** {m.get('msg', '')}")

                    actions = fused.get('actions', [])
                    if actions:
                        st.markdown('**LEAD Actions**')
                        for a in actions:
                            st.write(f"- {a.get('uav_id')} → `{a.get('action')}` — {a.get('reason', '')}")

                    swarm = apply_swarm_actions(
                        swarm,
                        actions,
                        threat_zone_km,
                        profile,
                        temperature_c,
                        wind_speed_kmh,
                        gustiness,
                        terrain_penalty,
                        stealth_drag_penalty,
                    )

                    st.markdown('**Updated Swarm State**')
                    for s in swarm:
                        zone_flag = '🟥 IN ZONE' if s.inside_threat_zone else ''
                        st.write(
                            f"- {s.id} [{s.role}] — End {s.endurance_min:.1f} min | "
                            f"Batt {s.battery_wh:.1f} Wh | Fuel {s.fuel_l:.2f} L | "
                            f"Alt {s.altitude_m} m | Speed {s.speed_kmh:.1f} km/h | "
                            f"Pos ({s.x_km:+.2f},{s.y_km:+.2f}) km | {s.status_note} {zone_flag}"
                        )
                st.subheader('Mission Playback')
                dt_s = 60.0
                swarm_history = []
                current_swarm = [VehicleState(**asdict(s)) for s in swarm]
                for _ in range(playback_minutes + 1):
                    swarm_history.append([asdict(s) for s in current_swarm])
                    current_swarm = simulate_swarm_step(current_swarm, dt_s, threat_zone_km)

                frame = st.slider('Playback Minute', 0, playback_minutes, 0)
                frame_swarm = [VehicleState(**data) for data in swarm_history[frame]]

                for s in frame_swarm:
                    zone_flag = '🟥 IN ZONE' if s.inside_threat_zone else ''
                    st.write(
                        f"- {s.id} [{s.role}] — End {s.endurance_min:.1f} min | "
                        f"Batt {s.battery_wh:.1f} Wh | Fuel {s.fuel_l:.2f} L | "
                        f"Alt {s.altitude_m} m | Speed {s.speed_kmh:.1f} km/h | "
                        f"Pos ({s.x_km:+.2f},{s.y_km:+.2f}) km | {s.status_note} {zone_flag}"
                    )

                fig = plot_swarm_map(frame_swarm, threat_zone_km, True, waypoints)
                st.pyplot(fig)
                plt.close(fig)

                rows = []
                for t, snapshot in enumerate(swarm_history):
                    for s in snapshot:
                        rows.append(
                            {
                                'time_min': t,
                                'uav_id': s['id'],
                                'role': s['role'],
                                'platform': s['platform'],
                                'power_system': s['power_system'],
                                'x_km': s['x_km'],
                                'y_km': s['y_km'],
                                'altitude_m': s['altitude_m'],
                                'speed_kmh': s['speed_kmh'],
                                'endurance_min': s['endurance_min'],
                                'battery_wh': s['battery_wh'],
                                'fuel_l': s['fuel_l'],
                                'draw_W': s['draw_W'],
                                'fuel_burn_lph': s['fuel_burn_lph'],
                                'delta_T': s['delta_T'],
                                'inside_threat_zone': s['inside_threat_zone'],
                                'current_wp': s['current_wp'],
                                'status_note': s['status_note'],
                            }
                        )

                swarm_df = pd.DataFrame(rows)
                st.download_button(
                    'Download Swarm Playback CSV',
                    data=swarm_df.to_csv(index=False).encode('utf-8'),
                    file_name='swarm_mission_playback.csv',
                    mime='text/csv',
                )

                if waypoints:
                    wp_df = pd.DataFrame(waypoints, columns=['x_km', 'y_km'])
                    st.download_button(
                        'Download Mission Waypoints CSV',
                        data=wp_df.to_csv(index=False).encode('utf-8'),
                        file_name='mission_waypoints.csv',
                        mime='text/csv',
                    )

        st.caption('GPT-UAV Planner | Built by Tareq Omrani | 2025')
    except Exception as e:
        st.error('Unexpected error during simulation.')
        if debug_mode:
            st.exception(e)
