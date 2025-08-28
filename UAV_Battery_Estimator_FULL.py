# Final1_full_mobile.py
# Streamlit UAV Mission Lab — Physics + LLM + Swarm + Stealth + Playback + CSV/JSON Exports
# Aerospace-minded upgrades applied globally:
# - ISA air-density everywhere; rotorcraft scaling √(ρ0/ρ)
# - Fixed-wing (battery & ICE) use drag polar (CD0 + k CL^2) + propulsive efficiency
# - Nonlinear gust/turbulence penalty vs wing loading & gust intensity
# - Convective + radiative thermal model (stable, never negative)
# - Climb energy exact (m·g·h) with recovery on descent (battery) and fuel for ICE
# - Battery clamped to platform nominal unless Debug Override
# - Endurance uncertainty bands (±10%)
# - Results export (CSV + JSON) with all key factors (density, wind penalty, climb cost)

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

# Auto-select text on focus (mobile-friendly)
st.markdown("""
    <script>
    const inputs = window.parent.document.querySelectorAll('input');
    inputs.forEach(el => el.addEventListener('focus', function(){ this.select(); }));
    </script>
""", unsafe_allow_html=True)

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
# Physics helpers
# ─────────────────────────────────────────────────────────
RHO0 = 1.225  # kg/m^3 sea-level
SIGMA = 5.670374419e-8  # Stefan–Boltzmann constant

def std_atmo_density(alt_m: float) -> float:
    """Simple exponential ISA-like density model, adequate up to ~6–8 km."""
    rho0, H = RHO0, 8500.0
    return rho0 * math.exp(-max(0.0, alt_m) / H)

def density_ratio(alt_m: float) -> Tuple[float, float]:
    """Return (rho, rho_ratio=rho/rho0)."""
    rho = std_atmo_density(alt_m)
    return rho, rho / RHO0

def rotorcraft_density_scale(rho_ratio: float) -> float:
    """Ideal induced-power scaling for rotors: P_induced ∝ 1/sqrt(ρ)."""
    return 1.0 / max(0.3, math.sqrt(max(1e-4, rho_ratio)))

def drag_polar_cd(cd0: float, cl: float, e: float, aspect_ratio: float) -> float:
    """Parasitic + induced drag model."""
    k = 1.0 / (math.pi * max(0.3, e) * max(2.0, aspect_ratio))
    return cd0 + k * (cl ** 2)

def aero_power_required_W(weight_N: float, rho: float, V_ms: float,
                          wing_area_m2: float, cd0: float, e: float,
                          wingspan_m: float, prop_eff: float) -> float:
    """
    Shaft power required using classic drag polar + dynamic pressure.
    """
    V_ms = max(1.0, V_ms)
    q = 0.5 * rho * V_ms * V_ms
    cl = weight_N / (q * max(1e-6, wing_area_m2))
    AR = (wingspan_m ** 2) / max(1e-6, wing_area_m2)
    cd = drag_polar_cd(cd0, cl, e, AR)
    D = q * wing_area_m2 * cd
    return (D * V_ms) / max(0.1, prop_eff)

def bsfc_fuel_burn_lph(power_W: float, bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    fuel_kg_per_h = (bsfc_gpkwh / 1000.0) * (power_W / 1000.0)
    return fuel_kg_per_h / max(0.5, fuel_density_kgpl)

def climb_fuel_liters(total_mass_kg: float, climb_m: float,
                      bsfc_gpkwh: float, fuel_density_kgpl: float) -> float:
    if climb_m <= 0: return 0.0
    E_kWh = (total_mass_kg * 9.81 * climb_m) / 3_600_000.0
    fuel_kg = (bsfc_gpkwh / 1000.0) * E_kWh
    return fuel_kg / max(0.5, fuel_density_kgpl)

def convective_radiative_deltaT(draw_watt: float, efficiency: float,
                                surface_area_m2: float, emissivity: float,
                                ambient_C: float, rho: float, V_ms: float) -> float:
    """
    Robust thermal model that never returns negative:
    Q = draw*(1-η). Solve ΔT from steady-state convective + radiative sink.
    h ≈ 8 W/m²K * (ρ/ρ0)^0.8 * (V/5)^{0.5}
    Radiative linearization: q_rad ≈ 4 ε σ T_amb^3 ΔT
    """
    Q = max(0.0, draw_watt * (1.0 - max(0.0, min(1.0, efficiency))))
    if Q <= 1e-6 or surface_area_m2 <= 1e-6 or emissivity <= 1e-3:
        return 0.0
    h0 = 8.0  # baseline convective coeff at ~5 m/s
    h = h0 * (max(0.2, rho / RHO0) ** 0.8) * (max(0.2, V_ms / 5.0) ** 0.5)
    T_amb = ambient_C + 273.15
    rad_coeff = 4.0 * emissivity * SIGMA * (T_amb ** 3)
    denom = (h * surface_area_m2) + (rad_coeff * surface_area_m2)
    dT = Q / max(1.0, denom)
    return max(0.0, dT)

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

def calculate_hybrid_draw(total_draw_watts, power_system):
    """Keeps interface consistent with legacy; no hybrid battery platforms here by default."""
    return total_draw_watts * 0.10 if str(power_system).lower() == "hybrid" else total_draw_watts

def calculate_fuel_consumption(power_draw_watt, duration_hr, fuel_burn_rate_lph=1.5):
    return fuel_burn_rate_lph * duration_hr if power_draw_watt > 0 else 0

# ─────────────────────────────────────────────────────────
# UAV profiles (FULL SET; add aero params & type for all)
# type: "rotor" or "fixed"
# For fixed: include wing_area_m2, wingspan_m, cd0, oswald_e, prop_eff
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
        "wing_area_m2": 0.76, "wingspan_m": 2.8,
        "cd0": 0.030, "oswald_e": 0.80, "prop_eff": 0.78,
        "ai_capabilities": "AI-enhanced ISR mission planning, autonomous loitering",
        "crash_risk": False
    },
    "Teal Golden Eagle": {
        "type": "fixed",
        "max_payload_g": 2000, "base_weight_kg": 2.2,
        "power_system": "Battery", "draw_watt": 220, "battery_wh": 100,
        "wing_area_m2": 0.30, "wingspan_m": 2.1,
        "cd0": 0.035, "oswald_e": 0.78, "prop_eff": 0.76,
        "ai_capabilities": "AI-driven ISR, edge-based visual classification, GPS-denied flight",
        "crash_risk": True
    },
    "Quantum Systems Vector": {
        "type": "fixed",
        "max_payload_g": 1500, "base_weight_kg": 2.3,
        "power_system": "Battery", "draw_watt": 160, "battery_wh": 150,
        "wing_area_m2": 0.55, "wingspan_m": 2.8,
        "cd0": 0.032, "oswald_e": 0.82, "prop_eff": 0.80,
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

with st.form("uav_form"):
    st.subheader("Flight Parameters")
    battery_capacity_wh = numeric_input("Battery Capacity (Wh)", float(profile["battery_wh"]))
    payload_weight_g = int(numeric_input("Payload (g)", int(profile["max_payload_g"]*0.5)))
    flight_speed_kmh = numeric_input("Speed (km/h)", 30.0)
    wind_speed_kmh = numeric_input("Wind (km/h)", 10.0)
    temperature_c = numeric_input("Temperature (°C)", 25.0)
    altitude_m = int(numeric_input("Altitude (m)", 0))
    elevation_gain_m = int(numeric_input("Elevation Gain (m)", 0))

    flight_mode = st.selectbox("Flight Mode", ["Hover","Forward Flight","Waypoint Mission"])
    cloud_cover = st.slider("Cloud Cover (%)", 0, 100, 50)
    gustiness = st.slider("Gust Factor", 0, 10, 2)
    terrain_penalty = st.slider("Terrain Complexity", 1.0, 1.5, 1.1)
    stealth_drag_penalty = st.slider("Stealth Drag Factor", 1.0, 1.5, 1.0)
    simulate_failure = st.checkbox("Enable Failure Simulation")

    # ICE panel for MQ-1 / MQ-9
    ice_params = None
    if drone_model in ["MQ-1 Predator", "MQ-9 Reaper"]:
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
- Endurance: {params['endurance_min']:.1f} min
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

# ─────────────────────────────────────────────────────────
# Utility: clamp battery/fuel to platform nominal (unless debug override)
# ─────────────────────────────────────────────────────────
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

        # Battery clamp unless override
        if profile["power_system"] == "Battery":
            battery_capacity_wh = clamp_battery(profile, battery_capacity_wh, allow_pack_override)

        total_weight_kg = profile["base_weight_kg"] + (payload_weight_g / 1000.0)

        # Simple temperature derate for cells
        if temperature_c < 15: battery_capacity_wh *= 0.90
        elif temperature_c > 35: battery_capacity_wh *= 0.95

        rho, rho_ratio = density_ratio(altitude_m)
        V_ms = max(1.0, (flight_speed_kmh / 3.6))
        weight_N = total_weight_kg * 9.81
        use_ice_branch = drone_model in ["MQ-1 Predator","MQ-9 Reaper"] and ice_params is not None

        # Atmosphere & factors
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
            P_req_W = aero_power_required_W(
                weight_N=weight_N, rho=rho, V_ms=V_ms,
                wing_area_m2=ice_params["wing_area_m2"],
                cd0=ice_params["cd0"], e=ice_params["oswald_e"],
                wingspan_m=ice_params["wingspan_m"], prop_eff=ice_params["prop_eff"]
            )

            # Gust penalty via wing loading
            WL = weight_N / max(0.05, ice_params["wing_area_m2"])
            wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms, WL)
            st.markdown(f"**Wind Turbulence Penalty:** `{wind_penalty_frac*100:.1f}%` added draw")
            P_req_W *= (1.0 + wind_penalty_frac)

            # Terrain/stealth penalties
            P_req_W *= terrain_penalty * stealth_drag_penalty

            # Fuel burn at required power
            lph = bsfc_fuel_burn_lph(P_req_W, ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"])

            # Climb fuel (mgh)
            climb_L = climb_fuel_liters(total_weight_kg, max(0, elevation_gain_m),
                                        ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"])
            if climb_L > 0:
                st.markdown(f"**Climb Energy Cost (fuel):** `{climb_L:.2f} L`")

            fuel_available_L = max(0.0, ice_params["fuel_tank_l"] - climb_L)

            # Hybrid assist (optional)
            if ice_params["hybrid_assist"]:
                battery_support_Wh = profile.get("battery_wh", 200.0)
                assist_power_W = P_req_W * ice_params["assist_fraction"]
                assist_energy_Wh = assist_power_W * (ice_params["assist_duration_min"] / 60.0)
                if assist_energy_Wh > battery_support_Wh:
                    ice_params["assist_duration_min"] = (battery_support_Wh / max(1.0, assist_power_W)) * 60.0
                    assist_energy_Wh = battery_support_Wh
                fuel_saved_L = bsfc_fuel_burn_lph(assist_power_W, ice_params["bsfc_gpkwh"], ice_params["fuel_density_kgpl"]) * (ice_params["assist_duration_min"] / 60.0)
                fuel_available_L += fuel_saved_L
                st.markdown(f"**Hybrid Assist Active:** {ice_params['assist_fraction']*100:.0f}% for {ice_params['assist_duration_min']:.1f} min")
                st.markdown(f"Battery used: {assist_energy_Wh:.1f} Wh  Fuel saved: {fuel_saved_L:.2f} L")

            endurance_hr = fuel_available_L / max(0.05, lph)
            flight_time_minutes = max(0.1, endurance_hr * 60.0)

            # Thermal model (convective+radiative)
            delta_T = convective_radiative_deltaT(P_req_W, 0.85, 0.6, 0.85, temperature_c, rho, V_ms)
            delta_T *= (1.0 - (cloud_cover / 100.0) * 0.35)
            if ice_params["hybrid_assist"] and ice_params["assist_duration_min"] > 0:
                delta_T *= (1.0 - ice_params["assist_fraction"] * 0.4)
                st.markdown(f"**Hybrid Assist IR Reduction:** ~{ice_params['assist_fraction']*40:.0f}%")

            # Uncertainty band (±10%)
            lo = flight_time_minutes * 0.90
            hi = flight_time_minutes * 1.10

            st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
            st.caption(f"Uncertainty band: {lo:.1f}–{hi:.1f} min (±10%)")
            if flight_mode != "Hover":
                st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

            st.subheader("Thermal & Fuel (ICE)")
            st.metric("Power Required (shaft)", f"{P_req_W/1000:.1f} kW")
            st.metric("Fuel Burn", f"{lph:.2f} L/hr")
            if climb_L > 0: st.markdown(f"**Climb Fuel Penalty:** `{climb_L:.2f} L` deducted")
            st.metric("Fuel Tank (usable)", f"{fuel_available_L:.1f} L")
            st.metric("Thermal ΔT", f"{delta_T:.1f} °C")

            # Live fuel sim (capped)
            st.subheader("Live Simulation (Fuel)")
            time_step=10
            total_steps=min(max(1, int(flight_time_minutes*60/time_step)), 300)
            fuel_per_sec=lph/3600.0
            progress=st.progress(0); status=st.empty(); gauge=st.empty(); timer=st.empty()
            for step in range(total_steps+1):
                elapsed=step*time_step
                fuel_rem=max(0.0, fuel_available_L - fuel_per_sec*elapsed)
                pct=0.0 if fuel_available_L<=0 else max(0.0, (fuel_rem/fuel_available_L)*100.0)
                bars=int(pct//10)
                gauge.markdown(f"**Fuel Gauge:** `[{'|'*bars}{' '*(10-bars)}] {pct:.0f}%`")
                remain=max(0.0, (flight_time_minutes*60)-elapsed)
                timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** {int(remain)} sec")
                status.markdown(f"**Fuel Remaining:** {fuel_rem:.2f} L  **Burn:** {lph:.2f} L/hr  **Power:** {P_req_W/1000:.1f} kW")
                progress.progress(min(step/total_steps,1.0))
                if fuel_rem<=0.0: break
                time.sleep(0.03)

            if simulate_failure or (delta_T > 15 or altitude_m > 100):
                st.warning("**Threat Alert:** UAV may be visible to AI-based IR/radar." + (" (Hybrid assist reduces IR.)" if ice_params["hybrid_assist"] else ""))
            else:
                st.success("**Safe:** Below typical detection thresholds.")

            computed_power_draw_for_llm = P_req_W
            computed_fuel_context_for_llm = fuel_available_L
            climb_energy_Wh = None  # ICE uses liters for climb cost
            wind_penalty_pct = wind_penalty_frac * 100.0

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
                st.markdown(f"**Wind Turbulence Penalty:** `{wind_penalty_frac*100:.1f}%` added draw")
                total_draw *= (1.0 + wind_penalty_frac)
            else:
                # Fixed-wing battery: use aero model like ICE
                wing_area_m2 = float(profile.get("wing_area_m2", 0.5))
                wingspan_m = float(profile.get("wingspan_m", 2.0))
                cd0 = float(profile.get("cd0", 0.03))
                e = float(profile.get("oswald_e", 0.80))
                prop_eff = float(profile.get("prop_eff", 0.78))
                # "Hover" not physical for fixed-wing; treat as low-speed loiter
                V_ms_eff = max(8.0, 0.6 * V_ms) if flight_mode == "Hover" else V_ms
                total_draw = aero_power_required_W(
                    weight_N=weight_N, rho=rho, V_ms=V_ms_eff,
                    wing_area_m2=wing_area_m2, cd0=cd0, e=e,
                    wingspan_m=wingspan_m, prop_eff=prop_eff
                )
                WL = weight_N / max(0.05, wing_area_m2)
                wind_penalty_frac = gust_penalty_fraction(gustiness, wind_speed_kmh, V_ms_eff, WL)
                total_draw *= (1.0 + wind_penalty_frac)
                st.markdown(f"**Wind Turbulence Penalty:** `{wind_penalty_frac*100:.1f}%` added draw")

            # Terrain & stealth
            total_draw *= terrain_penalty * stealth_drag_penalty

            # Climb/Descent energy for battery
            climb_energy_Wh = 0.0
            if elevation_gain_m > 0:
                climb_energy_Wh = (total_weight_kg * 9.81 * elevation_gain_m) / 3600.0
                battery_capacity_wh -= climb_energy_Wh
                st.markdown(f"**Climb Energy Cost:** `{climb_energy_Wh:.2f} Wh`")
                if battery_capacity_wh <= 0: st.error("Simulation stopped: climb energy exceeds battery capacity."); st.stop()
            elif elevation_gain_m < 0:
                recov = (total_weight_kg * 9.81 * abs(elevation_gain_m) / 3600.0) * 0.20
                battery_capacity_wh += recov; st.markdown(f"**Descent Recovery:** `+{recov:.2f} Wh`")

            batt_draw = calculate_hybrid_draw(total_draw, profile["power_system"])
            if batt_draw <= 0: st.error("Simulation failed: Battery draw is zero or undefined."); st.stop()

            # Thermal (convective+radiative)
            delta_T = convective_radiative_deltaT(total_draw, 0.87, 0.30, 0.90, temperature_c, rho, V_ms)
            delta_T *= (1.0 - (cloud_cover / 100.0) * 0.35)

            # Endurance + uncertainty
            flight_time_minutes = (battery_capacity_wh / batt_draw) * 60.0
            lo = flight_time_minutes * 0.90
            hi = flight_time_minutes * 1.10

            st.metric("Estimated Flight Time", f"{flight_time_minutes:.1f} minutes")
            st.caption(f"Uncertainty band: {lo:.1f}–{hi:.1f} min (±10%)")
            if flight_mode != "Hover":
                st.metric("Estimated Max Distance", f"{(flight_time_minutes / 60) * flight_speed_kmh:.2f} km")

            st.subheader("Thermal Signature & Fuel Analysis")
            st.metric("Thermal Signature Risk", f"{'Low' if delta_T < 10 else ('Moderate' if delta_T < 20 else 'High')} (ΔT = {delta_T:.1f}°C)")
            st.info("Fuel tracking not applicable for battery-only UAVs.")

            # Live battery sim (capped)
            st.subheader("Live Simulation (Battery)")
            time_step=10
            total_steps=min(max(1, int(flight_time_minutes*60/time_step)), 300)
            battery_per_step=(total_draw*time_step)/3600
            progress=st.progress(0); status=st.empty(); gauge=st.empty(); timer=st.empty()
            for step in range(total_steps+1):
                elapsed=step*time_step
                batt_rem=battery_capacity_wh-(step*battery_per_step)
                if batt_rem<=0:
                    gauge.markdown(f"**Battery Gauge:** `[{' ' * 10}] 0%`")
                    timer.markdown(f"**Elapsed:** {elapsed} sec **Remaining:** 0 sec")
                    status.markdown(f"**Battery Remaining:** 0.00 Wh  **Power Draw:** {total_draw:.0f} W")
                    progress.progress(1.0); break
                batt_pct=max(0,(batt_rem/battery_capacity_wh)*100)
                bars=int(batt_pct//10)
                gauge.markdown(f"**Battery Gauge:** `[{'|'*bars}{' '*(10-bars)}] {batt_pct:.0f}%`")
                remain=max(0,(flight_time_minutes*60)-elapsed)
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

        # ───────── Mission Advisor ─────────
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
            base_batt_wh = float(max(10.0, battery_capacity_wh if profile["power_system"]=="Battery" else 200.0))
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

            # CSV export for playback
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

        # ───────── Export Results (CSV + JSON + Copy-Paste) ─────────
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
            "Climb Energy (Wh)": round(climb_energy_Wh, 2) if (profile["power_system"]=="Battery" and climb_energy_Wh is not None) else None,
            "Climb Fuel (L)": round(climb_L, 2) if (use_ice_branch and 'climb_L' in locals()) else None,
            "Terrain Factor": float(terrain_penalty),
            "Stealth Drag Factor": float(stealth_drag_penalty),
            "Estimated Flight Time (min)": round(flight_time_minutes, 1),
            "Estimated Max Distance (km)": round((flight_time_minutes/60.0)*flight_speed_kmh, 2) if flight_mode != "Hover" else 0.0,
            "ΔT (°C)": round(delta_T, 1),
            "Endurance Band Low (min)": round(lo, 1),
            "Endurance Band High (min)": round(hi, 1)
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

        # ───────── AI Suggestions (classic tips) ─────────
        st.subheader("AI Suggestions (Simulated GPT)")
        if payload_weight_g == profile["max_payload_g"]:
            st.write("**Tip:** Payload is at maximum lift capacity.")
        if wind_speed_kmh > 15:
            st.write("**Tip:** High wind may reduce flight time.")
        if profile["power_system"]=="Battery" and battery_capacity_wh < 30:
            st.write("**Tip:** Battery is under 30 Wh. Consider a larger pack.")
        if flight_mode in ["Hover", "Waypoint Mission"]:
            st.write("**Tip:** Hover and waypoint missions draw extra power.")
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
