# Final1_full_mobile.py
# UAV Battery Efficiency Estimator — Aerospace-grade physics + LLM + Swarm + Stealth + Playback + CSV/JSON Export
# Global upgrades applied to ALL UAV models:
# - ISA air-density; rotorcraft induced-power √(ρ0/ρ) scaling
# - Fixed-wing battery & ICE: bounded aero (CD0 floor, e cap, ηp bounds) + hotel loads + installation losses
# - Gust/turbulence penalty vs wing loading or rotor WL proxy
# - Vector wind groundspeed: best-heading & upwind ranges (warn if W ≥ V_air)
# - Energy realism: 85% usable battery + 30% dispatch reserve (battery), 90% usable tank + 30% reserve (ICE)
# - Climb energy (battery Wh) / climb fuel (ICE L) applied explicitly
# - Robust thermal model with convection floor; waste heat includes hotel load
# - Full swarm advisor/LEAD fusion retained; unified CSV/JSON export
# - Title fixed to “UAV Battery Efficiency Estimator” in digital green; duplicate headers removed
# - “Hover” removed from fixed-wing; “Loiter” added (fixed & rotor)

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

# Auto-select text when focusing an input (easier to clear/edit on mobile)
st.markdown("""
    <script>
    const inputs = window.parent.document.querySelectorAll('input');
    inputs.forEach(el => el.addEventListener('focus', function(){ this.select(); }));
    </script>
""", unsafe_allow_html=True)

# Single title (digital green) — no duplicates
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
# Physics helpers (aerospace-grade)
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

def heading_range_km(V_air_ms: float, W_ms: float, t_min: float) -> Tuple[float,float]:
    """Return (best_km, worst_km). Worst=0 if upwind infeasible (W ≥ V_air)."""
    t_h = max(0.0, t_min) / 60.0
    if V_air_ms <= 0.1:
        return (0.0, 0.0)
    if W_ms >= V_air_ms:
        return ((V_air_ms + W_ms) * t_h / 1000.0, 0.0)
    worst = (V_air_ms - W_ms) * t_h / 1000.0
    best  = (V_air_ms + W_ms) * t_h / 1000.0
    return (best, worst)

def convective_radiative_deltaT(Q_w: float, surface_area_m2: float, emissivity: float,
                                ambient_C: float, rho: float, V_ms: float) -> float:
    """
    Robust thermal model:
    - Q_w is waste heat in watts (all electrical + avionics eventually → heat).
    - Convection: conservative floor; scales with ρ and V.
    - Radiation: linearized effective sink near ambient.
    """
    if Q_w <= 0.0 or surface_area_m2 <= 0.0 or emissivity <= 0.0:
        return 0.0
    V_ms = max(0.5, V_ms)
    h = max(6.0, 10.45 - V_ms + 10 * math.sqrt(V_ms)) * (rho / RHO0)  # W/m²K
    T_ambK = ambient_C + 273.15
    rad_coeff = 4.0 * emissivity * SIGMA * (T_ambK ** 3)  # W/m²K
    sink_W_per_K = (h + rad_coeff) * surface_area_m2
    dT = Q_w / max(1.0, sink_W_per_K)
    return max(0.2, dT)

def climb_energy_wh(total_mass_kg: float, climb_m: float) -> float:
    """Battery: m g h converted to Wh (1 Wh = 3600 J)."""
    if climb_m <= 0: return 0.0
    return (total_mass_kg * 9.81 * climb_m) / 3600.0

def bsfc_fuel_burn_lph(power_W: float, bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    """ICE: fuel burn (L/h) from shaft power and BSFC."""
    fuel_kg_per_h = (bsfc_gpkwh / 1000.0) * (power_W / 1000.0)
    return fuel_kg_per_h / max(0.5, fuel_density_kgpl)

def climb_fuel_liters(total_mass_kg: float, climb_m: float,
                      bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    """ICE: convert m g h to required fuel via BSFC (kWh)."""
    if climb_m <= 0: return 0.0
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
# Form
# ─────────────────────────────────────────────────────────
debug_mode = st.checkbox("Enable Debug Mode")
allow_pack_override = st.checkbox("Allow Battery Override (debug)", value=False) if debug_mode else False

drone_model = st.selectbox("Drone Model", list(UAV_PROFILES.keys()))
profile = UAV_PROFILES[drone_model]

st.info(f"**AI Capabilities:** {profile['ai_capabilities']}")
st.caption(f"Base weight: {profile['base_weight_kg']} kg — Max payload: {profile['max_payload_g']} g")
st.caption(f"Power system: `{profile['power_system']}` | Type: `{profile['type']}`")

# Dynamic flight modes:
# - Fixed-wing: Forward Flight, Loiter, Waypoint Mission (no Hover)
# - Rotor/VTOL: Hover, Forward Flight, Loiter, Waypoint Mission
if profile["type"] == "fixed":
    flight_mode_options = ["Forward Flight", "Loiter", "Waypoint Mission"]
else:
    flight_mode_options = ["Hover", "Forward Flight", "Loiter", "Waypoint Mission"]

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = numeric_input("Battery Capacity (Wh)", float(profile["battery_wh"]))
    payload_weight_g = int(numeric_input("Payload (g)", int(profile["max_payload_g"]*0.5)))
    flight_speed_kmh = numeric_input("Speed (km/h)", 30.0)
    wind_speed_kmh = numeric_input("Wind (km/h)", 10.0)
    temperature_c = numeric_input("Temperature (°C)", 25.0)
    altitude_m = int(numeric_input("Altitude (m)", 0))
    elevation_gain_m = int(numeric_input("Elevation Gain (m)", 0))

    flight_mode = st.selectbox("Flight Mode", flight_mode_options)
    cloud_cover = st.slider("Cloud Cover (%)", 0, 100, 50)
    gustiness = st.slider("Gust Factor", 0, 10, 2)
    terrain_penalty = st.slider("Terrain Complexity", 1.0, 1.5, 1.1)
    stealth_drag_penalty = st.slider("Stealth Drag Factor", 1.0, 1.5, 1.0)
    simulate_failure = st.checkbox("Enable Failure Simulation")

    # ICE panel for MQ-1 / MQ-9
    ice_params = None
    if profile["power_system"] == "ICE":
        st.markdown("### Aerospace Model (ICE-only)")
        fuel_tank_l = numeric_input("Fuel Tank (L)", float(profile.get("fuel_tank_l", 300.0)))
        cd0 = numeric_input("C_D0 (parasite)", float(profile.get("cd0", 0.025)))
        wing_area_m2 = numeric_input("Wing Area S (m²)", float(profile.get("wing_area_m2", 11.5)))
        wingspan_m = numeric_input("Wingspan b (m)", float(profile.get("wingspan_m", 14.8)))
        oswald_e = numeric_input("Oswald e", float(profile.get("oswald_e", 0.80)))
        prop_eff = numeric_input("Propulsive η_p", float(profile.get("prop_eff", 0.80)))
        bsfc_gpkwh = numeric_input("BSFC (g/kWh)", float(profile.get("bsfc_gpkwh", 260.0)))
        fuel_density_kgpl = numeric_input("Fuel Density (kg/L)", float(profile.get("fuel_density_kgpl", 0.72)))
        hybrid_assist = st.checkbox("Enable Hybrid Assist (experimental)")
        assist_fraction = st.slider("Assist Fraction", 0.05, 0.30, 0.10, step=0.01)
        assist_duration_min = st.slider("Assist Duration (minutes)", 1, 30, 10)

        ice_params = dict(
            fuel_tank_l=fuel_tank_l, wing_area_m2=wing_area_m2, wingspan_m=wingspan_m,
            cd0=cd0, oswald_e=oswald_e, prop_eff=prop_eff,
            bsfc_gpkwh=bsfc_gpkwh, fuel_density_kgpl=fuel_density_kgpl,
            hybrid_assist=hybrid_assist, assist_fraction=assist_fraction,
            assist_duration_min=assist_duration_min
        )
    else:
        hybrid_assist = False
        assist_fraction = 0.0
        assist_duration_min = 0

    submitted = st.form_submit_button("Estimate")

# Swarm & Stealth controls
st.markdown("### Swarm & Stealth")
swarm_enable = st.checkbox("Enable Swarm Advisor", value=True)
swarm_size = st.slider("Swarm Size", 2, 8, 3)
swarm_steps = st.slider("Swarm Conversation Rounds", 1, 5, 2)
stealth_ingress = st.checkbox("Enable Stealth Ingress Mode", value=True)
threat_zone_km = st.slider("Threat Zone Radius (km)", 1.0, 20.0, 5.0)

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
# LLM Mission Advisor
# ─────────────────────────────────────────────────────────
def generate_llm_advice(params):
    if not OPENAI_AVAILABLE:
        return ("LLM unavailable — heuristic advice:\n"
                "- Reduce payload for longer endurance.\n"
                "- Lower altitude or speed in gusty winds.\n"
                "- Use hybrid assist during ingress to cut IR.\n"
                "- Loiter under cloud where possible.")
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
                "- Descend 100–200 m if gusts rise.\n"
                "- Engage assist only in high-threat sectors.")

# ─────────────────────────────────────────────────────────
# Swarm (multi-agent) scaffolding
# ─────────────────────────────────────────────────────────
ALLOWED_ACTIONS = ["RTB","LOITER","HANDOFF_TRACK","RELOCATE","ALTITUDE_CHANGE","SPEED_CHANGE","RELAY_COMMS","STANDBY","HYBRID_ASSIST"]

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

def summarize_state(s: AgentState) -> Dict[str, Any]:
    d = asdict(s).copy(); d.pop("waypoints", None); return d

def seed_swarm(n, base_endurance, base_batt_wh, delta_T, altitude_m, platform) -> List[AgentState]:
    roles = ["LEAD","SCOUT","TRACKER","RELAY","STRIKER"]
    out=[]
    for i in range(n):
        role=roles[i%len(roles)]
        out.append(AgentState(
            id=f"UAV_{i+1}", role=role, platform=platform,
            endurance_min=float(random.uniform(0.7,1.1)*max(5.0, base_endurance)),
            battery_wh=float(random.uniform(0.8,1.1)*max(10.0, base_batt_wh)),
            fuel_l=float(random.uniform(70.0,200.0) if "MQ-" in platform else random.uniform(5.0,25.0)),
            speed_kmh=float(random.uniform(25,40)), altitude_m=int(altitude_m+random.uniform(-20,20)),
            x_km=float(random.uniform(-1,1)), y_km=float(random.uniform(-1,1)),
            delta_T=float(delta_T*random.uniform(0.9,1.2))
        ))
    return out

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

def _safe_json(txt: str) -> Dict[str, Any]:
    try: return json.loads(txt)
    except Exception:
        s,e=txt.find("{"), txt.rfind("}")
        return json.loads(txt[s:e+1])

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

def apply_actions(swarm: List[AgentState], acts: List[Dict[str,Any]],
                  stealth_ingress: bool, threat_zone_km: float) -> List[AgentState]:
    def in_zone(s: AgentState) -> bool:
        return (s.x_km**2 + s.y_km**2)**0.5 <= threat_zone_km
    idx = {s.id: s for s in swarm}
    for a in acts:
        s = idx.get(a.get("uav_id")); 
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

# Map
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

def clamp_battery(platform: Dict[str, Any], requested_wh: float, allow_override: bool) -> float:
    nominal = float(platform.get("battery_wh", requested_wh))
    if allow_override:
        return max(0.0, requested_wh)
    if requested_wh > nominal:
        st.warning(f"Battery clamped to platform nominal: {nominal:.0f} Wh (requested {requested_wh:.0f} Wh).")
    return max(0.0, min(requested_wh, nominal))

# ─────────────────────────────────────────────────────────
# Simulation + Results
# ─────────────────────────────────────────────────────────
if submitted:
    try:
        if payload_weight_g > profile["max_payload_g"]:
            st.error("Payload exceeds lift capacity."); st.stop()

        # Clamp battery unless override
        if profile["power_system"] == "Battery":
            battery_capacity_wh = clamp_battery(profile, battery_capacity_wh, allow_pack_override)

        total_weight_kg = profile["base_weight_kg"] + (payload_weight_g / 1000.0)
        start_batt_wh_for_gauge = battery_capacity_wh  # for correct % depletion visualization
        V_ms = max(1.0, (flight_speed_kmh / 3.6))
        rho, rho_ratio = density_ratio(altitude_m, temperature_c)
        weight_N = total_weight_kg * 9.81
        W_ms = max(0.0, wind_speed_kmh / 3.6)
        use_ice_branch = profile["power_system"] == "ICE" and (ice_params is not None)

        # Temperature derate for cells
        if profile["power_system"] == "Battery":
            if temperature_c < 15: battery_capacity_wh *= 0.90
            elif temperature_c > 35: battery_capacity_wh *= 0.95
            start_batt_wh_for_gauge = battery_capacity_wh  # update after temp derate

        # Atmosphere & key factors
        st.header("Atmospheric Conditions")
        st.metric("Air Density ρ", f"{rho:.3f} kg/m³")
        st.metric("Density Ratio ρ/ρ₀", f"{rho_ratio:.3f}")

        st.header("Applied Environment Factors")
        if profile["type"] == "rotor":
            density_factor = rotorcraft_density_scale(rho_ratio)
            st.markdown(f"**Air density factor:** `{rho_ratio:.3f}` (ρ/ρ₀)  —  **Rotor power factor:** `{density_factor:.3f}` (∝ 1/√ρ)")
        else:
            st.markdown(f"**Air density factor:** `{rho_ratio:.3f}` (ρ/ρ₀) — handled via lift/drag in aero model.")

        # ───────── ICE aerospace branch ─────────
        if use_ice_branch:
            # Aero power (bounded aero for realism)
            CD0   = max(0.05, ice_params["cd0"])
            E_OSW = min(0.70, ice_params["oswald_e"])
            ETA_P = min(0.65, max(0.55, ice_params["prop_eff"]))
            # Effective speed for Loiter (fixed-wing) — slower endurance speed
            V_ms_eff = V_ms
            if flight_mode == "Loiter":
                V_ms_eff = max(8.0, 0.6 * V_ms)

            P_req_W = aero_power_required_W(
                weight_N=weight_N, rho=rho, V_ms=V_ms_eff,
                wing_area_m2=ice_params["wing_area_m2"],
                cd0=CD0, e=E_OSW,
                wingspan_m=ice_params["wingspan_m"], prop_eff=ETA_P
            )
            # Maneuvering penalties by mission mode
            if flight_mode == "Waypoint Mission":
                P_req_W *= 1.05
            elif flight_mode == "Loiter":
                P_req_W *= 1.10

            # Gust penalty via wing loading
            WL = weight_N / max(0.05, ice_params["wing_area_m2"])
            wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms_eff, WL)
            st.markdown(f"**Wind Turbulence Penalty:** `{wind_penalty_frac*100:.1f}%` added power")
            P_req_W *= (1.0 + wind_penalty_frac)

            # Terrain/stealth penalties
            P_req_W *= terrain_penalty * stealth_drag_penalty

            # Add hotel load to shaft demand (electrical systems)
            HOTEL_W = HOTEL_W_DEFAULT
            P_total_W = P_req_W + HOTEL_W

            # Fuel burn at total power
            lph = bsfc_fuel_burn_lph(P_total_W, ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"])

            # Climb fuel (mgh)
            climb_L_val = climb_fuel_liters(total_weight_kg, max(0, elevation_gain_m),
                                            ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"])
            if climb_L_val > 0:
                st.markdown(f"**Climb Energy Cost (fuel):** `{climb_L_val:.2f} L`")
            else:
                st.markdown("**Climb Energy Cost (fuel):** `0.00 L`")

            # Usable fuel fraction + reserve
            usable_fuel_L_start = max(0.0, ice_params["fuel_tank_l"] * USABLE_FUEL_FRAC - max(0.0, climb_L_val))
            usable_fuel_L = usable_fuel_L_start

            # Optional hybrid assist (battery substitution for a slice of power)
            if ice_params["hybrid_assist"]:
                battery_support_Wh = profile.get("battery_wh", 200.0)
                assist_power_W = P_total_W * ice_params["assist_fraction"]
                assist_energy_Wh = assist_power_W * (ice_params["assist_duration_min"] / 60.0)
                if assist_energy_Wh > battery_support_Wh:
                    ice_params["assist_duration_min"] = (battery_support_Wh / max(1.0, assist_power_W)) * 60.0
                    assist_energy_Wh = battery_support_Wh
                # Fuel saved during assist
                fuel_saved_L = bsfc_fuel_burn_lph(assist_power_W, ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"]) * (ice_params["assist_duration_min"] / 60.0)
                usable_fuel_L += fuel_saved_L
                st.markdown(f"**Hybrid Assist Active:** {ice_params['assist_fraction']*100:.0f}% for {ice_params['assist_duration_min']:.1f} min")
                st.markdown(f"Battery used: {assist_energy_Wh:.1f} Wh  Fuel saved: {fuel_saved_L:.2f} L")

            raw_endurance_hr = usable_fuel_L / max(0.05, lph)
            raw_endurance_min = raw_endurance_hr * 60.0
            dispatch_endurance_min = raw_endurance_min * (1.0 - DISPATCH_RESERVE)

            # Vector-wind ranges on dispatchable endurance
            best_km, worst_km = heading_range_km(V_ms_eff, W_ms, dispatch_endurance_min)
            if W_ms > V_ms_eff:
                st.warning("Wind exceeds airspeed: upwind leg infeasible (groundspeed ≤ 0).")

            # Thermal model (use total power as waste heat proxy)
            Q_waste = P_total_W  # conservative
            delta_T = convective_radiative_deltaT(Q_waste, 0.6, 0.85, temperature_c, rho, V_ms_eff)
            delta_T *= (1.0 - (cloud_cover / 100.0) * 0.35)
            if ice_params["hybrid_assist"] and ice_params["assist_duration_min"] > 0:
                delta_T *= (1.0 - ice_params["assist_fraction"] * 0.3)
                st.markdown(f"**Hybrid Assist IR Reduction:** ~{ice_params['assist_fraction']*30:.0f}%")

            # Uncertainty band (±10%)
            lo = dispatch_endurance_min * 0.90
            hi = dispatch_endurance_min * 1.10

            st.metric("Dispatchable Endurance", f"{dispatch_endurance_min:.1f} minutes")
            st.caption(f"Uncertainty band: {lo:.1f}–{hi:.1f} min (±10%)")
            st.metric("Best Heading Range", f"{best_km:.1f} km")
            st.metric("Upwind Range", f"{worst_km:.1f} km")

            st.subheader("Thermal & Fuel (ICE)")
            st.metric("Total Power (shaft+hotel)", f"{P_total_W/1000:.2f} kW")
            st.metric("Fuel Burn", f"{lph:.2f} L/hr")
            st.metric("Usable Fuel (after climb)", f"{usable_fuel_L:.2f} L")
            st.metric("Thermal ΔT", f"{delta_T:.1f} °C")

            # Live fuel sim (capped) — percent uses starting usable fuel for correct gauge
            st.subheader("Live Simulation (Fuel)")
            time_step=10
            total_steps=min(max(1, int(dispatch_endurance_min*60/time_step)), 300)
            fuel_per_sec=lph/3600.0
            progress=st.progress(0); status=st.empty(); gauge=st.empty(); timer=st.empty()
            for step in range(total_steps+1):
                elapsed=step*time_step
                fuel_rem=max(0.0, usable_fuel_L_start - fuel_per_sec*elapsed)
                pct=0.0 if usable_fuel_L_start<=0 else max(0.0, (fuel_rem/usable_fuel_L_start)*100.0)
                bars=int(pct//10)
                gauge.markdown(f"**Fuel Gauge:** `[{'|'*bars}{' '*(10-bars)}] {pct:.0f}%`")
                remain=max(0.0, (dispatch_endurance_min*60)-elapsed)
                timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** {int(remain)} sec")
                status.markdown(f"**Fuel Remaining:** {fuel_rem:.2f} L  **Burn:** {lph:.2f} L/hr  **Power:** {P_total_W/1000:.2f} kW")
                progress.progress(min(step/total_steps,1.0))
                if fuel_rem<=0.0: break
                time.sleep(0.03)

            if simulate_failure or (delta_T > 15 or altitude_m > 100):
                st.warning("**Threat Alert:** UAV may be visible to AI-based IR/radar." + (" (Hybrid assist reduces IR.)" if ice_params["hybrid_assist"] else ""))
            else:
                st.success("**Safe:** Below typical detection thresholds.")

            computed_power_draw_for_llm = P_total_W
            computed_fuel_context_for_llm = usable_fuel_L
            wind_penalty_pct = wind_penalty_frac * 100.0
            climb_energy_Wh_value = None  # ICE uses liters for climb cost
            flight_time_minutes = dispatch_endurance_min  # used for swarm seeding
            climb_L = climb_L_val

        # ───────── Battery/Hybrid (global) ─────────
        else:
            if profile["type"] == "rotor":
                # Rotorcraft: base draw scaled by mass & density + parasitic ~V^2
                base_draw = profile.get("draw_watt", 180.0)
                weight_factor = total_weight_kg / max(0.1, profile["base_weight_kg"])
                density_factor = rotorcraft_density_scale(rho_ratio)  # √(ρ0/ρ)
                V_term = 0.018 * (flight_speed_kmh ** 2)
                total_draw = (base_draw * weight_factor * density_factor) + V_term
                # Gust penalty (rotor WL proxy)
                WL_proxy = float(profile.get("rotor_WL_proxy", 45.0))
                wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms, WL_proxy)
                total_draw *= (1.0 + wind_penalty_frac)
                st.markdown(f"**Wind Turbulence Penalty:** `{wind_penalty_frac*100:.1f}%` added power")

                # Mission penalties
                if flight_mode == "Waypoint Mission":
                    total_draw *= 1.05
                elif flight_mode == "Loiter":
                    total_draw *= 1.08  # mild extra load in steady circling
                elif flight_mode == "Hover":
                    total_draw *= 1.10  # small reserve for station-keeping

            else:
                # Fixed-wing battery: bounded aero + hotel + install losses
                wing_area_m2 = float(profile.get("wing_area_m2", 0.5))
                wingspan_m   = float(profile.get("wingspan_m", 2.0))
                cd0          = float(profile.get("cd0", 0.05))
                e            = float(profile.get("oswald_e", 0.70))
                prop_eff     = float(profile.get("prop_eff", 0.60))

                # Loiter modeled as low-speed endurance setting
                if flight_mode == "Loiter":
                    V_ms_eff = max(8.0, 0.6 * V_ms)
                else:
                    V_ms_eff = V_ms

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
                st.markdown(f"**Wind Turbulence Penalty:** `{wind_penalty_frac*100:.1f}%` added power")

                # Mission penalties
                if flight_mode == "Waypoint Mission":
                    total_draw *= 1.05
                elif flight_mode == "Loiter":
                    total_draw *= 1.10

            # Terrain & stealth
            total_draw *= terrain_penalty * stealth_drag_penalty

            # Climb/Descent energy for battery
            climb_energy_Wh_value = 0.0
            if elevation_gain_m > 0:
                climb_energy_Wh_value = climb_energy_wh(total_weight_kg, elevation_gain_m)
                battery_capacity_wh -= climb_energy_Wh_value
                st.markdown(f"**Climb Energy Cost:** `{climb_energy_Wh_value:.2f} Wh`")
                if battery_capacity_wh <= 0: 
                    st.error("Simulation stopped: climb energy exceeds available battery capacity."); 
                    st.stop()
                # Update start gauge to reflect immediate deduction at T0
                start_batt_wh_for_gauge = battery_capacity_wh
            elif elevation_gain_m < 0:
                recov = (total_weight_kg * 9.81 * abs(elevation_gain_m) / 3600.0) * 0.20
                battery_capacity_wh += recov
                start_batt_wh_for_gauge = battery_capacity_wh
                st.markdown(f"**Descent Recovery:** `+{recov:.2f} Wh`")

            # Usable energy + reserve
            usable_Wh = max(0.0, battery_capacity_wh) * USABLE_BATT_FRAC
            t_raw_min = (usable_Wh / max(5.0, total_draw)) * 60.0
            dispatch_endurance_min = t_raw_min * (1.0 - DISPATCH_RESERVE)

            # Vector wind ranges (based on V_ms or loiter V)
            V_ref_ms = V_ms if profile["type"] == "rotor" else (max(8.0, 0.6*V_ms) if flight_mode=="Loiter" else V_ms)
            best_km, worst_km = heading_range_km(V_ref_ms, W_ms, dispatch_endurance_min)
            if W_ms > V_ref_ms:
                st.warning("Wind exceeds airspeed: upwind leg infeasible (groundspeed ≤ 0).")

            # Thermal (waste heat = total draw + hotel)
            Q_waste = total_draw + HOTEL_W_DEFAULT
            ref_surface = 0.30 if profile["type"] == "rotor" else 0.35
            delta_T = convective_radiative_deltaT(Q_waste, ref_surface, 0.90, temperature_c, rho, V_ref_ms)
            delta_T *= (1.0 - (cloud_cover / 100.0) * 0.35)

            # Uncertainty band (±10%)
            lo = dispatch_endurance_min * 0.90
            hi = dispatch_endurance_min * 1.10

            st.metric("Dispatchable Endurance", f"{dispatch_endurance_min:.1f} minutes")
            st.caption(f"Uncertainty band: {lo:.1f}–{hi:.1f} min (±10%)")
            st.metric("Best Heading Range", f"{best_km:.1f} km")
            st.metric("Upwind Range", f"{worst_km:.1f} km")

            st.subheader("Thermal Signature & Fuel Analysis")
            risk = 'Low' if delta_T < 10 else ('Moderate' if delta_T < 20 else 'High')
            st.metric("Thermal Signature Risk", f"{risk} (ΔT = {delta_T:.1f}°C)")
            st.info("Fuel tracking not applicable for battery-only UAVs.")

            # Live battery sim (capped) — percent uses starting battery Wh for correct gauge
            st.subheader("Live Simulation (Battery)")
            time_step=10
            total_steps=min(max(1, int(dispatch_endurance_min*60/time_step)), 300)
            battery_per_step=(total_draw*time_step)/3600
            progress=st.progress(0); status=st.empty(); gauge=st.empty(); timer=st.empty()
            for step in range(total_steps+1):
                elapsed=step*time_step
                batt_rem=start_batt_wh_for_gauge-(step*battery_per_step)
                if batt_rem<=0:
                    gauge.markdown(f"**Battery Gauge:** `[{' ' * 10}] 0%`")
                    timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** 0 sec")
                    status.markdown(f"**Battery Remaining:** 0.00 Wh  **Power Draw:** {total_draw:.0f} W")
                    progress.progress(1.0); break
                batt_pct=max(0,(batt_rem/start_batt_wh_for_gauge)*100)
                bars=int(batt_pct//10)
                gauge.markdown(f"**Battery Gauge:** `[{'|'*bars}{' '*(10-bars)}] {batt_pct:.0f}%`")
                remain=max(0,(dispatch_endurance_min*60)-elapsed)
                timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** {int(remain)} sec")
                status.markdown(f"**Battery Remaining:** {batt_rem:.2f} Wh  **Power Draw:** {total_draw:.0f} W")
                progress.progress(min(step/total_steps,1.0))
                time.sleep(0.03)

            if simulate_failure or (delta_T > 15 or altitude_m > 100):
                st.warning("**Threat Alert:** UAV may be visible to AI-based IR/radar.")
            else:
                st.success("**Safe:** Below typical detection thresholds.")

            computed_power_draw_for_llm = total_draw
            computed_fuel_context_for_llm = 0.0
            wind_penalty_pct = wind_penalty_frac * 100.0
            climb_L = None
            flight_time_minutes = dispatch_endurance_min  # used for swarm seeding

        # ───────── Mission Advisor (LLM) ─────────
        st.subheader("AI Mission Advisor (LLM)")
        params = {
            "drone":drone_model, "payload_g":payload_weight_g, "mode":flight_mode,
            "speed_kmh":flight_speed_kmh, "alt_m":altitude_m,
            "wind_kmh":wind_speed_kmh, "gust":gustiness,
            "endurance_min":flight_time_minutes, "delta_T":delta_T,
            "fuel_l":computed_fuel_context_for_llm,
            "hybrid_assist": (use_ice_branch and ice_params.get("hybrid_assist", False)) if use_ice_branch else False,
            "assist_fraction": (ice_params.get("assist_fraction",0.0) if use_ice_branch else 0.0),
            "assist_duration_min": (ice_params.get("assist_duration_min",0) if use_ice_branch else 0)
        }
        st.write(generate_llm_advice(params))

        # ───────── Swarm Advisor ─────────
        if swarm_enable:
            st.header("Swarm Advisor (Multi-Agent LLM)")
            base_endurance = float(max(5.0, flight_time_minutes))
            base_batt_wh = float(max(10.0, (battery_capacity_wh if profile["power_system"]=="Battery" else 200.0)))
            swarm = seed_swarm(swarm_size, base_endurance, base_batt_wh, delta_T, altitude_m, platform=drone_model)
            for s in swarm:
                s.waypoints = waypoints.copy()
                s.current_wp = 0

            st.write("**Initial Swarm State**")
            for s in swarm:
                st.write(f"- {s.id} [{s.role}] ({s.platform}) — End {s.endurance_min:.1f} min | "
                         f"Fuel {s.fuel_l:.1f} L | Alt {s.altitude_m} m | Pos ({s.x_km:+.1f},{s.y_km:+.1f}) km | ΔT {s.delta_T:.1f}°C")

            env = {
                "wind_kmh": wind_speed_kmh, "gust": gustiness, "mission": flight_mode,
                "threat_note": ("elevated" if (simulate_failure or delta_T > 15 or altitude_m > 100) else "normal"),
                "stealth_ingress": stealth_ingress, "threat_zone_km": threat_zone_km
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
                        st.write(f"- {a.get('uav_id')} → `{a.get('action')}` — {a.get('reason','')}")
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
                    s.fuel_l = max(0, s.fuel_l - random.uniform(1.0, 2.0))
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

            fig = plot_swarm_map(frame_swarm, threat_zone_km, stealth_ingress, waypoints)
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
            if waypoints:
                wp_df = pd.DataFrame(waypoints, columns=["x_km","y_km"])
                st.download_button(
                    "Download Mission Waypoints CSV",
                    data=wp_df.to_csv(index=False).encode("utf-8"),
                    file_name="mission_waypoints.csv",
                    mime="text/csv"
                )

        # ───────── Export Scenario Results (CSV + JSON) ─────────
        st.subheader("Export Scenario Results")
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
            "Wind Penalty (%)": round(wind_penalty_pct, 1) if 'wind_penalty_pct' in locals() else 0.0,
            "Climb Energy (Wh)": round(climb_energy_Wh_value, 2) if (profile["power_system"]=="Battery") else None,
            "Climb Fuel (L)": round(climb_L, 2) if (use_ice_branch and 'climb_L' in locals() and climb_L is not None) else None,
            "Terrain Factor": float(terrain_penalty),
            "Stealth Drag Factor": float(stealth_drag_penalty),
            "Dispatchable Endurance (min)": round(flight_time_minutes, 1),
            "Best Heading Range (km)": round(best_km, 2),
            "Upwind Range (km)": round(worst_km, 2),
            "ΔT (°C)": round(delta_T, 1)
        }

        df_res = pd.DataFrame([results])
        csv_buffer = io.BytesIO()
        df_res.to_csv(csv_buffer, index=False)
        st.download_button(
            "⬇️ Download Results CSV",
            data=csv_buffer,
            file_name="mission_results.csv",
            mime="text/csv"
        )

        json_str = json.dumps(results, indent=2)
        st.download_button(
            "⬇️ Download Results JSON",
            data=json_str,
            file_name="mission_results.json",
            mime="application/json"
        )
        st.text_area("Results (JSON Copy-Paste)", json_str, height=250)

        # ───────── AI Suggestions (Simulated GPT) ─────────
        st.subheader("AI Suggestions (Simulated GPT)")
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
        if delta_T > 15:
            st.write("**Tip:** Thermal load is high. Consider lighter payload or lower altitude.")
        if altitude_m > 100:
            st.write("**Tip:** Flying above 100m may increase detection risk.")
        if gustiness >= 5:
            st.write("**Tip:** Gust factor above 5 may destabilize small UAVs.")

        st.caption("GPT-UAV Planner | Built by Tareq Omrani | 2025")

    except Exception as e:
        st.error("Unexpected error during simulation.")
        if debug_mode:
            st.exception(e)
