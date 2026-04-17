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
.mission-hero {
  background: linear-gradient(135deg, rgba(17,24,39,0.96), rgba(11,18,32,0.96));
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 16px 18px;
  margin: 10px 0 14px 0;
  box-shadow: 0 14px 34px rgba(0,0,0,0.18);
}
.mission-hero-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 12px;
  margin-top: 10px;
}
.mission-kicker {
  color: var(--accent-2);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.10em;
  text-transform: uppercase;
}
.mission-label {
  color: var(--accent);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.mission-value {
  color: var(--text);
  font-size: 1.15rem;
  font-weight: 800;
}
@media (max-width: 900px) {
  .mission-hero-grid {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }
}
</style>
""", unsafe_allow_html=True)

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


def run_detectability_autopilot(
    enabled: bool,
    overall_score: float,
    visual_score: float,
    thermal_score: float,
    confidence: float,
    altitude_m: int,
    speed_kmh: float,
    power_system: str,
    hybrid_assist_enabled: bool = False,
    stealth_drag_penalty: float = 1.0,
) -> Dict[str, Any]:
    """Heuristic detectability-aware autopilot recommendations."""
    result = {
        "enabled": enabled,
        "active": False,
        "target_speed_kmh": float(speed_kmh),
        "target_altitude_m": int(altitude_m),
        "hybrid_assist_recommend": False,
        "actions": [],
    }
    if not enabled:
        return result

    if confidence < 55:
        result["actions"].append("Low confidence in detectability estimate — autopilot changes held conservative.")

    if visual_score >= 70:
        result["active"] = True
        result["target_altitude_m"] = int(altitude_m + 200)
        result["target_speed_kmh"] = max(20.0, speed_kmh * 0.88)
        result["actions"].append("Visual risk high — recommend +200 m altitude and ~12% speed reduction.")
    elif visual_score >= 55:
        result["active"] = True
        result["target_altitude_m"] = int(altitude_m + 100)
        result["target_speed_kmh"] = max(20.0, speed_kmh * 0.94)
        result["actions"].append("Visual risk elevated — recommend +100 m altitude and mild speed reduction.")

    if thermal_score >= 70:
        result["active"] = True
        result["target_speed_kmh"] = max(20.0, min(result["target_speed_kmh"], speed_kmh * 0.90))
        result["actions"].append("Thermal risk high — recommend reduced sustained power / speed.")
        if power_system == "ICE" and hybrid_assist_enabled:
            result["hybrid_assist_recommend"] = True
            result["actions"].append("Hybrid Assist recommended during ingress / threat exposure.")
    elif thermal_score >= 55:
        result["active"] = True
        result["actions"].append("Thermal risk elevated — avoid prolonged climb or high-power segments.")

    if overall_score >= 80 and not result["active"]:
        result["active"] = True
        result["target_speed_kmh"] = max(20.0, speed_kmh * 0.90)
        result["target_altitude_m"] = int(altitude_m + 150)
        result["actions"].append("Overall detectability very high — recommend conservative profile adjustment.")

    if stealth_drag_penalty > 1.2:
        result["actions"].append("Stealth drag penalty is high — monitor reserve margins after autopilot changes.")

    return result


def render_detectability_autopilot_panel(ap: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Detectability-Aware Autopilot</div>"
        "<div class='section-note'>Automatic mission-profile recommendations that bias speed, altitude, and hybrid usage under high exposure.</div></div>",
        unsafe_allow_html=True,
    )
    if not ap.get("enabled", False):
        st.info("Detectability Autopilot is disabled.")
        return

    if ap.get("active", False):
        st.success("Autopilot advisory: ACTIVE")
    else:
        st.info("Autopilot advisory: NOMINAL")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Target Speed", f"{ap.get('target_speed_kmh', 0.0):.1f} km/h")
    with c2:
        st.metric("Target Altitude", f"{int(ap.get('target_altitude_m', 0))} m")
    with c3:
        st.metric("Hybrid Assist", "RECOMMEND" if ap.get("hybrid_assist_recommend", False) else "NO CHANGE")

    for action in ap.get("actions", []):
        if "high" in action.lower() or "recommended" in action.lower():
            st.warning(action)
        else:
            st.info(action)



def compute_route_metrics(waypoints: List[Tuple[float, float]]) -> Dict[str, float]:
    if not waypoints:
        return {"total_distance_km": 0.0, "segment_count": 0, "max_leg_km": 0.0}
    pts = [(0.0, 0.0)] + list(waypoints)
    dists = []
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i-1][0]
        dy = pts[i][1] - pts[i-1][1]
        d = (dx**2 + dy**2) ** 0.5
        dists.append(d)
    return {
        "total_distance_km": float(sum(dists)),
        "segment_count": len(dists),
        "max_leg_km": float(max(dists) if dists else 0.0),
    }


def score_route_candidate(
    distance_km: float,
    speed_kmh: float,
    overall_detectability: float,
    visual_detectability: float,
    thermal_detectability: float,
    terrain_penalty: float,
    stealth_drag_penalty: float,
    threat_zone_km: float,
    waypoints: List[Tuple[float, float]],
) -> Dict[str, float]:
    # Fraction of waypoints inside threat radius
    if waypoints:
        inside = sum(1 for x, y in waypoints if (x*x + y*y) ** 0.5 <= threat_zone_km)
        threat_fraction = inside / max(1, len(waypoints))
    else:
        threat_fraction = 0.0

    time_min = (distance_km / max(1.0, speed_kmh)) * 60.0
    exposure_cost = 0.55 * overall_detectability + 0.25 * visual_detectability + 20.0 * threat_fraction
    energy_cost = 12.0 * (terrain_penalty - 1.0) + 12.0 * (stealth_drag_penalty - 1.0) + 0.08 * distance_km
    time_cost = 0.25 * time_min + 0.02 * max(0.0, speed_kmh - 60.0)

    total_score = exposure_cost + energy_cost + time_cost
    return {
        "route_score": round(total_score, 2),
        "time_cost_min": round(time_min, 2),
        "threat_fraction": round(threat_fraction, 3),
        "exposure_cost": round(exposure_cost, 2),
        "energy_cost": round(energy_cost, 2),
        "time_cost": round(time_cost, 2),
    }


def optimize_route_profile(
    enabled: bool,
    waypoints: List[Tuple[float, float]],
    speed_kmh: float,
    altitude_m: int,
    overall_detectability: float,
    visual_detectability: float,
    thermal_detectability: float,
    terrain_penalty: float,
    stealth_drag_penalty: float,
    threat_zone_km: float,
    radar_threat_penalty: float = 0.0,
) -> Dict[str, Any]:
    route_metrics = compute_route_metrics(waypoints)
    base = score_route_candidate(
        distance_km=route_metrics["total_distance_km"],
        speed_kmh=speed_kmh,
        overall_detectability=overall_detectability,
        visual_detectability=visual_detectability,
        thermal_detectability=thermal_detectability,
        terrain_penalty=terrain_penalty,
        stealth_drag_penalty=stealth_drag_penalty,
        threat_zone_km=threat_zone_km,
        waypoints=waypoints,
    )

    base["route_score"] = round(base["route_score"] + float(radar_threat_penalty), 2)
    result = {
        "enabled": enabled,
        "active": False,
        "recommended_speed_kmh": float(speed_kmh),
        "recommended_altitude_m": int(altitude_m),
        "recommended_route_mode": "Direct",
        "base_score": base["route_score"],
        "optimized_score": base["route_score"],
        "route_metrics": route_metrics,
        "details": base,
        "actions": [],
    }
    if not enabled:
        return result

    # Candidate: stealth-biased route profile (slower, slightly higher)
    cand_speed = max(20.0, speed_kmh * 0.90)
    cand_alt = int(altitude_m + 150)
    cand = score_route_candidate(
        distance_km=route_metrics["total_distance_km"] * (1.05 if route_metrics["segment_count"] > 0 else 1.0),
        speed_kmh=cand_speed,
        overall_detectability=max(0.0, overall_detectability * 0.88),
        visual_detectability=max(0.0, visual_detectability * 0.86),
        thermal_detectability=max(0.0, thermal_detectability * 0.93),
        terrain_penalty=terrain_penalty,
        stealth_drag_penalty=stealth_drag_penalty,
        threat_zone_km=threat_zone_km,
        waypoints=waypoints,
    )

    if cand["route_score"] + 1.0 < base["route_score"]:
        result["active"] = True
        result["recommended_speed_kmh"] = round(cand_speed, 2)
        result["recommended_altitude_m"] = cand_alt
        result["recommended_route_mode"] = "Stealth-Biased"
        result["optimized_score"] = cand["route_score"]
        result["details"] = cand
        result["actions"].append("Optimized route profile favors lower exposure over raw transit speed.")
        if radar_threat_penalty > 0:
            result["actions"].append("Radar threat is elevating route cost — stealth-biased routing is weighted more heavily.")
        if cand["threat_fraction"] > 0:
            result["actions"].append("Threat-zone exposure remains nonzero; prefer terrain masking or revised waypoints where possible.")
    else:
        result["actions"].append("Current route profile is already near-optimal under the present weighting.")

    return result


def render_route_optimization_panel(route_opt: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Route Optimization</div>"
        "<div class='section-note'>Weighted route scoring using exposure, energy, and time costs. This is a planning heuristic, not a full pathfinding engine.</div></div>",
        unsafe_allow_html=True,
    )
    if not route_opt.get("enabled", False):
        st.info("Route Optimization is disabled.")
        return

    if route_opt.get("active", False):
        st.success("Route optimization advisory: ACTIVE")
    else:
        st.info("Route optimization advisory: NOMINAL")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Base Route Score", f"{route_opt.get('base_score', 0.0):.1f}")
    with c2:
        st.metric("Optimized Score", f"{route_opt.get('optimized_score', 0.0):.1f}")
    with c3:
        st.metric("Route Mode", route_opt.get("recommended_route_mode", "Direct"))

    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("Recommended Speed", f"{route_opt.get('recommended_speed_kmh', 0.0):.1f} km/h")
    with c5:
        st.metric("Recommended Altitude", f"{int(route_opt.get('recommended_altitude_m', 0))} m")
    with c6:
        st.metric("Route Distance", f"{route_opt.get('route_metrics', {}).get('total_distance_km', 0.0):.1f} km")

    d = route_opt.get("details", {})
    st.caption(
        f"Exposure cost: {d.get('exposure_cost', 0.0):.1f} | "
        f"Energy cost: {d.get('energy_cost', 0.0):.1f} | "
        f"Time cost: {d.get('time_cost', 0.0):.1f} | "
        f"Threat-zone fraction: {100*d.get('threat_fraction', 0.0):.0f}%"
    )

    for action in route_opt.get("actions", []):
        if "threat-zone" in action.lower():
            st.warning(action)
        else:
            st.info(action)



def upgrade_swarm_intelligence(enabled: bool, swarm: List[VehicleState], threat_zone_km: float) -> Dict[str, Any]:
    """Role-aware swarm upgrade with reassignment, resilience, and operator guidance."""
    result = {
        "enabled": enabled,
        "active": False,
        "swarm_score": 0.0,
        "resilience_score": 0.0,
        "actions": [],
        "reassignments": [],
        "team_summary": [],
    }
    if not enabled or not swarm:
        return result

    roles_present = set()
    low_endurance = []
    inside_zone = []
    relay_candidates = []
    scout_candidates = []
    tracker_candidates = []

    for s in swarm:
        role = getattr(s, "role", "UNKNOWN")
        roles_present.add(role)
        if float(getattr(s, "endurance_min", 0.0)) < 12.0:
            low_endurance.append(s.id)
        if (float(getattr(s, "x_km", 0.0))**2 + float(getattr(s, "y_km", 0.0))**2) ** 0.5 <= threat_zone_km:
            inside_zone.append(s.id)

        alt = int(getattr(s, "altitude_m", 0))
        endu = float(getattr(s, "endurance_min", 0.0))
        if alt >= 120 and endu >= 15:
            relay_candidates.append(s)
        if endu >= 14 and alt <= 120:
            scout_candidates.append(s)
        if endu >= 16:
            tracker_candidates.append(s)

    # Role coverage scoring
    desired_roles = {"LEAD", "SCOUT", "TRACKER", "RELAY"}
    coverage = len(desired_roles.intersection(roles_present)) / len(desired_roles)
    endurance_penalty = min(0.4, 0.05 * len(low_endurance))
    zone_penalty = min(0.3, 0.04 * len(inside_zone))
    resilience = max(0.0, 1.0 - endurance_penalty - zone_penalty)
    swarm_score = max(0.0, min(100.0, 100.0 * (0.55 * coverage + 0.45 * resilience)))

    result["active"] = True
    result["swarm_score"] = round(swarm_score, 1)
    result["resilience_score"] = round(100.0 * resilience, 1)

    # Dynamic reassignment recommendations
    if "RELAY" not in roles_present and relay_candidates:
        cand = sorted(relay_candidates, key=lambda s: (-float(getattr(s, "endurance_min", 0.0)), -int(getattr(s, "altitude_m", 0))))[0]
        result["reassignments"].append(f"{cand.id} → RELAY")
        result["actions"].append("Relay coverage missing — assign highest-altitude endurance UAV to RELAY.")
    if "SCOUT" not in roles_present and scout_candidates:
        cand = sorted(scout_candidates, key=lambda s: (-float(getattr(s, "endurance_min", 0.0)), int(getattr(s, "altitude_m", 0))))[0]
        result["reassignments"].append(f"{cand.id} → SCOUT")
        result["actions"].append("Scout coverage missing — assign low-altitude, high-endurance UAV to SCOUT.")
    if "TRACKER" not in roles_present and tracker_candidates:
        cand = sorted(tracker_candidates, key=lambda s: -float(getattr(s, "endurance_min", 0.0)))[0]
        result["reassignments"].append(f"{cand.id} → TRACKER")
        result["actions"].append("Tracking redundancy missing — assign highest-endurance UAV to TRACKER.")

    # Loss compensation / RTB logic
    if low_endurance:
        result["actions"].append("Low-endurance agents detected — prioritize RTB or comms relay handoff.")
        for uid in low_endurance[:2]:
            result["reassignments"].append(f"{uid} → STANDBY/RTB")

    if inside_zone:
        result["actions"].append("Threat-zone penetration detected — distribute roles to avoid single-point mission failure.")

    # Team summary
    result["team_summary"] = [
        f"Role coverage: {len(desired_roles.intersection(roles_present))}/{len(desired_roles)} critical roles",
        f"Low-endurance agents: {len(low_endurance)}",
        f"Threat-zone agents: {len(inside_zone)}",
    ]

    if result["swarm_score"] >= 75:
        result["actions"].append("Swarm posture is strong — maintain distributed coverage.")
    elif result["swarm_score"] >= 50:
        result["actions"].append("Swarm posture is moderate — improve role distribution and reserve margins.")
    else:
        result["actions"].append("Swarm posture is weak — mission resilience degraded; reduce exposure and consolidate tasks.")

    return result


def render_swarm_intelligence_panel(sw_intel: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Swarm Intelligence Upgrade</div>"
        "<div class='section-note'>Role-aware swarm analysis with reassignment guidance, resilience scoring, and loss-compensation recommendations.</div></div>",
        unsafe_allow_html=True,
    )
    if not sw_intel.get("enabled", False):
        st.info("Swarm Intelligence Upgrade is disabled.")
        return

    if sw_intel.get("swarm_score", 0.0) >= 75:
        st.success("Swarm intelligence status: STRONG")
    elif sw_intel.get("swarm_score", 0.0) >= 50:
        st.warning("Swarm intelligence status: MODERATE")
    else:
        st.error("Swarm intelligence status: DEGRADED")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Swarm Score", f"{sw_intel.get('swarm_score', 0.0):.1f}/100")
    with c2:
        st.metric("Resilience Score", f"{sw_intel.get('resilience_score', 0.0):.1f}/100")

    for line in sw_intel.get("team_summary", []):
        st.info(line)

    if sw_intel.get("reassignments"):
        st.markdown("**Recommended Reassignments**")
        for r in sw_intel["reassignments"]:
            st.write(f"- {r}")

    if sw_intel.get("actions"):
        st.markdown("**Swarm Actions**")
        for action in sw_intel["actions"]:
            if "degraded" in action.lower() or "rtb" in action.lower():
                st.warning(action)
            else:
                st.info(action)




def estimate_terrain_masking(
    enabled: bool,
    waypoints: List[Tuple[float, float]],
    altitude_m: int,
    terrain_penalty: float,
    cloud_cover: int,
    overall_detectability: float,
    visual_detectability: float,
    thermal_detectability: float,
    threat_zone_km: float,
    terrain_ridge_amplitude_m: float = 80.0,
) -> Dict[str, Any]:
    # Terrain Masking v2: segment-based LOS blocking / shadowing surrogate
    import math
    result = {
        "enabled": enabled,
        "active": False,
        "masking_score": 0.0,
        "concealment_fraction": 0.0,
        "shielding_factor": 1.0,
        "adjusted_visual_score": float(visual_detectability),
        "adjusted_overall_score": float(overall_detectability),
        "actions": [],
        "segments_in_masking_window": 0,
        "segment_summary": [],
        "segment_visibility_labels": [],
        "los_block_fraction": 0.0,
        "shadowed_distance_km": 0.0,
    }
    if not enabled:
        return result

    pts = [(0.0, 0.0)] + list(waypoints)
    segments = []
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i-1][0]
        dy = pts[i][1] - pts[i-1][1]
        d = (dx**2 + dy**2) ** 0.5
        segments.append((pts[i-1], pts[i], d))

    if not segments:
        return result

    terrain_complexity = max(0.0, min(1.0, (float(terrain_penalty) - 1.0) / 0.5))
    cloud_bonus = 0.12 * max(0.0, min(1.0, cloud_cover / 100.0))
    altitude_factor = max(0.0, min(1.0, (350.0 - float(altitude_m)) / 350.0))
    ridge_amp = max(0.0, float(terrain_ridge_amplitude_m))

    labels = []
    shadowed_distance = 0.0
    blocked_segments = 0
    masked_window = 0

    for idx, (p0, p1, d) in enumerate(segments, start=1):
        mx = 0.5 * (p0[0] + p1[0])
        my = 0.5 * (p0[1] + p1[1])
        mid_r = (mx*mx + my*my) ** 0.5

        # Surrogate ridge height: strongest near threat-zone ring and with terrain complexity
        ring_term = math.exp(-((mid_r - threat_zone_km) ** 2) / max(0.2, 0.35 * max(1.0, threat_zone_km)))
        ridge_height_m = ridge_amp * (0.45 + 0.55 * terrain_complexity) * ring_term

        # LOS clearance surrogate: lower altitude and higher ridges create blocking
        clearance_m = float(altitude_m) - ridge_height_m

        if mid_r <= threat_zone_km:
            masked_window += 1

        if clearance_m <= 0:
            label = "Shielded"
            blocked_segments += 1
            shadowed_distance += d
        elif clearance_m <= 0.35 * max(50.0, altitude_m):
            label = "Partial"
            shadowed_distance += 0.5 * d
        else:
            label = "Exposed"

        labels.append(label)

    segment_count = len(segments)
    los_block_fraction = blocked_segments / max(1, segment_count)
    partial_fraction = sum(1 for x in labels if x == "Partial") / max(1, segment_count)

    concealment_fraction = max(0.0, min(1.0,
        0.45 * los_block_fraction +
        0.22 * partial_fraction +
        0.18 * altitude_factor +
        0.08 * terrain_complexity +
        cloud_bonus
    ))

    shielding_factor = max(0.55, 1.0 - 0.42 * concealment_fraction - 0.10 * partial_fraction)
    adjusted_visual = max(0.0, float(visual_detectability) * shielding_factor)
    adjusted_overall = max(0.0, 0.60 * adjusted_visual + 0.40 * float(thermal_detectability))
    masking_score = 100.0 * concealment_fraction

    result.update({
        "active": concealment_fraction >= 0.15,
        "masking_score": round(masking_score, 1),
        "concealment_fraction": round(concealment_fraction, 3),
        "shielding_factor": round(shielding_factor, 3),
        "adjusted_visual_score": round(adjusted_visual, 1),
        "adjusted_overall_score": round(adjusted_overall, 1),
        "segments_in_masking_window": int(masked_window),
        "segment_visibility_labels": labels,
        "los_block_fraction": round(los_block_fraction, 3),
        "shadowed_distance_km": round(shadowed_distance, 3),
        "segment_summary": [
            f"Exposed: {sum(1 for x in labels if x == 'Exposed')}",
            f"Partial: {sum(1 for x in labels if x == 'Partial')}",
            f"Shielded: {sum(1 for x in labels if x == 'Shielded')}",
        ],
    })

    if los_block_fraction >= 0.40:
        result["actions"].append("Terrain LOS blocking is strong — multiple route legs are shielded from direct observation.")
    elif concealment_fraction >= 0.20:
        result["actions"].append("Terrain masking is moderate — some route legs gain partial or shadowed concealment.")
    else:
        result["actions"].append("Terrain masking is weak — most route legs remain exposed to line-of-sight observation.")

    if altitude_m > 350:
        result["actions"].append("Altitude is limiting terrain shielding — descend if mission allows for stronger LOS masking.")
    if terrain_penalty <= 1.05:
        result["actions"].append("Terrain complexity is low — limited ridge / valley shielding is available.")
    if shadowed_distance > 0:
        result["actions"].append(f"Approximate shadowed route distance: {shadowed_distance:.2f} km.")
    if adjusted_overall + 5 < overall_detectability:
        result["actions"].append("Terrain-shadowed routing lowers estimated exposure relative to the unmasked baseline.")

    return result


def render_terrain_masking_panel(tm: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Terrain Masking</div>"
        "<div class='section-note'>Planning-grade line-of-sight concealment estimate based on low-altitude routing, terrain complexity, and threat-zone exposure.</div></div>",
        unsafe_allow_html=True,
    )
    if not tm.get("enabled", False):
        st.info("Terrain Masking is disabled.")
        return

    if tm.get("active", False):
        st.success("Terrain masking status: ACTIVE")
    else:
        st.info("Terrain masking status: LIMITED")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Masking Score", f"{tm.get('masking_score', 0.0):.1f}/100")
    with c2:
        st.metric("Shielding Factor", f"{tm.get('shielding_factor', 1.0):.2f}")
    with c3:
        st.metric("LOS Block Fraction", f"{100*tm.get('los_block_fraction', 0.0):.0f}%")

    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("Adjusted Visual Score", f"{tm.get('adjusted_visual_score', 0.0):.1f}/100")
    with c5:
        st.metric("Adjusted Overall Score", f"{tm.get('adjusted_overall_score', 0.0):.1f}/100")
    with c6:
        st.metric("Shadowed Distance", f"{tm.get('shadowed_distance_km', 0.0):.2f} km")

    if tm.get('segment_summary'):
        st.markdown('**Segment LOS Summary**')
        for s in tm.get('segment_summary', []):
            st.write(f'- {s}')

    for action in tm.get("actions", []):
        if "weak" in action.lower() or "too high" in action.lower() or "limited" in action.lower():
            st.warning(action)
        else:
            st.info(action)



def compute_sensor_model(
    enabled: bool,
    sensor_band: str,
    sensor_quality: float,
    humidity_factor: float,
    cloud_cover: int,
    altitude_m: int,
    visual_score: float,
    thermal_score: float,
    overall_score: float,
    delta_t: float,
) -> Dict[str, Any]:
    """Planning-grade EO/IR sensor modeling."""
    result = {
        "enabled": enabled,
        "active": False,
        "sensor_band": sensor_band,
        "sensor_quality": float(sensor_quality),
        "ranges_km": [],
        "transmission": [],
        "contrast_curve": [],
        "probability_curve": [],
        "max_likely_detection_km": 0.0,
        "baseline_probability": 0.0,
        "actions": [],
    }
    if not enabled:
        return result

    import math

    band_beta = {"EO": 0.18, "MWIR": 0.11, "LWIR": 0.09}.get(sensor_band, 0.12)
    beta = band_beta * (1.0 + 0.9 * float(humidity_factor) + 0.5 * (cloud_cover / 100.0))

    if sensor_band == "EO":
        c0 = max(0.05, min(1.0, visual_score / 100.0))
        alpha = 0.030
        q_thresh = 0.26
    elif sensor_band == "MWIR":
        c0 = max(0.05, min(1.2, delta_t / 25.0))
        alpha = 0.022
        q_thresh = 0.22
    else:
        c0 = max(0.05, min(1.2, delta_t / 22.0))
        alpha = 0.018
        q_thresh = 0.20

    altitude_bonus = min(0.15, max(0.0, altitude_m / 2000.0) * 0.10)
    c0 *= (1.0 + altitude_bonus)

    ranges = [round(x * 0.5, 2) for x in range(1, 31)]
    transmission, contrast_curve, probability_curve = [], [], []

    for r in ranges:
        t_atm = math.exp(-beta * r)
        c_app = c0 * t_atm * (1.0 / (1.0 + alpha * (r ** 2)))
        logit = 8.0 * ((c_app * float(sensor_quality)) - q_thresh)
        p_det = 1.0 / (1.0 + math.exp(-logit))
        transmission.append(round(t_atm, 4))
        contrast_curve.append(round(c_app, 4))
        probability_curve.append(round(100.0 * p_det, 2))

    max_det_km = 0.0
    for r, p in zip(ranges, probability_curve):
        if p >= 50.0:
            max_det_km = r

    baseline_probability = probability_curve[0] if probability_curve else 0.0

    result.update({
        "active": True,
        "ranges_km": ranges,
        "transmission": transmission,
        "contrast_curve": contrast_curve,
        "probability_curve": probability_curve,
        "max_likely_detection_km": round(max_det_km, 2),
        "baseline_probability": round(baseline_probability, 1),
    })

    if max_det_km >= 8.0:
        result["actions"].append("Sensor threat is strong at long range — reduce exposure and favor masking.")
    elif max_det_km >= 4.0:
        result["actions"].append("Moderate detection range — use altitude, cloud cover, and route shaping to manage exposure.")
    else:
        result["actions"].append("Short likely detection range — present conditions are favorable for reduced observability.")

    if humidity_factor > 0.7 or cloud_cover > 70:
        result["actions"].append("Atmospheric attenuation is helping suppress long-range sensor performance.")
    if sensor_band == "EO" and visual_score > 65:
        result["actions"].append("EO exposure remains significant — avoid prolonged straight-line transit in clear conditions.")
    if sensor_band in ["MWIR", "LWIR"] and thermal_score > 65:
        result["actions"].append("IR contrast is strong — reduce sustained power or use Hybrid Assist during ingress.")
    return result


def render_sensor_modeling_panel(sensor_profile: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Sensor Modeling</div>"
        "<div class='section-note'>Planning-grade EO/IR detection probability model using atmospheric attenuation, apparent contrast, and sensor quality.</div></div>",
        unsafe_allow_html=True,
    )
    if not sensor_profile.get("enabled", False):
        st.info("Sensor Modeling is disabled.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Sensor Band", sensor_profile.get("sensor_band", "EO"))
    with c2:
        st.metric("Sensor Quality", f"{sensor_profile.get('sensor_quality', 1.0):.2f}")
    with c3:
        st.metric("Likely Detection Range", f"{sensor_profile.get('max_likely_detection_km', 0.0):.1f} km")

    c4, c5 = st.columns(2)
    with c4:
        st.metric("Near-Range Detection", f"{sensor_profile.get('baseline_probability', 0.0):.0f}%")
    with c5:
        st.metric("Curve Points", f"{len(sensor_profile.get('ranges_km', []))}")

    if sensor_profile.get("ranges_km"):
        fig_s1, ax_s1 = plt.subplots(figsize=(6.5, 3.2))
        ax_s1.plot(sensor_profile["ranges_km"], sensor_profile["probability_curve"])
        ax_s1.set_xlabel("Range (km)")
        ax_s1.set_ylabel("Detection Probability (%)")
        ax_s1.set_ylim(0, 100)
        ax_s1.set_title("Detection Probability vs Range")
        st.pyplot(fig_s1, clear_figure=True)
        plt.close(fig_s1)

        fig_s2, ax_s2 = plt.subplots(figsize=(6.5, 3.2))
        ax_s2.plot(sensor_profile["ranges_km"], sensor_profile["contrast_curve"])
        ax_s2.set_xlabel("Range (km)")
        ax_s2.set_ylabel("Apparent Contrast")
        ax_s2.set_title("Contrast vs Range")
        st.pyplot(fig_s2, clear_figure=True)
        plt.close(fig_s2)

        fig_s3, ax_s3 = plt.subplots(figsize=(6.5, 3.2))
        ax_s3.plot(sensor_profile["ranges_km"], sensor_profile["transmission"])
        ax_s3.set_xlabel("Range (km)")
        ax_s3.set_ylabel("Transmission")
        ax_s3.set_ylim(0, 1.05)
        ax_s3.set_title("Atmospheric Transmission vs Range")
        st.pyplot(fig_s3, clear_figure=True)
        plt.close(fig_s3)

    for action in sensor_profile.get("actions", []):
        if "strong" in action.lower() or "significant" in action.lower():
            st.warning(action)
        else:
            st.info(action)



def build_mission_path_frames(
    waypoints: List[Tuple[float, float]],
    altitude_m: int,
    num_frames: int = 30,
) -> List[Dict[str, float]]:
    pts = [(0.0, 0.0)] + list(waypoints)
    if len(pts) < 2:
        return [{"x_km": 0.0, "y_km": 0.0, "altitude_m": float(altitude_m)}]

    # Segment lengths
    segs = []
    total_dist = 0.0
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i-1][0]
        dy = pts[i][1] - pts[i-1][1]
        d = (dx**2 + dy**2) ** 0.5
        segs.append((pts[i-1], pts[i], d))
        total_dist += d

    if total_dist <= 1e-6:
        return [{"x_km": 0.0, "y_km": 0.0, "altitude_m": float(altitude_m)}]

    frames = []
    for k in range(num_frames):
        target_dist = total_dist * (k / max(1, num_frames - 1))
        walked = 0.0
        pos = (pts[0][0], pts[0][1])
        for p0, p1, d in segs:
            if walked + d >= target_dist and d > 0:
                frac = (target_dist - walked) / d
                x = p0[0] + frac * (p1[0] - p0[0])
                y = p0[1] + frac * (p1[1] - p0[1])
                pos = (x, y)
                break
            walked += d
            pos = p1
        frames.append({"x_km": float(pos[0]), "y_km": float(pos[1]), "altitude_m": float(altitude_m)})
    return frames


def compute_detectability_heatmap(
    extent_km: float,
    overall_score: float,
    visual_score: float,
    thermal_score: float,
    threat_zone_km: float,
    grid_n: int = 60,
):
    import numpy as np
    xs = np.linspace(-extent_km, extent_km, grid_n)
    ys = np.linspace(-extent_km, extent_km, grid_n)
    X, Y = np.meshgrid(xs, ys)
    R = np.sqrt(X**2 + Y**2)

    # Threat-centered exposure field, bounded to 0..100
    base = 0.50 * float(overall_score) + 0.30 * float(visual_score) + 0.20 * float(thermal_score)
    threat_core = np.exp(-((R / max(0.5, threat_zone_km)) ** 2))
    ring = np.exp(-((R - threat_zone_km) ** 2) / max(0.25, 0.35 * threat_zone_km))
    Z = base * (0.55 * threat_core + 0.25 * ring + 0.20)
    Z = np.clip(Z, 0.0, 100.0)
    return xs, ys, Z


def render_mission_visualization_panel(
    enabled: bool,
    waypoints: List[Tuple[float, float]],
    altitude_m: int,
    overall_score: float,
    visual_score: float,
    thermal_score: float,
    threat_zone_km: float,
    swarm_history: Optional[List[List[Dict[str, Any]]]] = None,
    nav_estimated_path: Optional[List[Tuple[float, float]]] = None,
):
    st.markdown(
        "<div class='section-card'><div class='section-title'>2D/3D Mission Visualization</div>"
        "<div class='section-note'>Animated mission-path frame view, detectability heatmap, and swarm movement visualization.</div></div>",
        unsafe_allow_html=True,
    )
    if not enabled:
        st.info("2D/3D Mission Visualization is disabled.")
        return

    import numpy as np
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    path_frames = build_mission_path_frames(waypoints, altitude_m, num_frames=30)
    max_frame = len(path_frames) - 1
    frame_idx = st.slider("Mission Visualization Frame", 0, max_frame, 0)
    frame = path_frames[frame_idx]

    # 2D animated path view
    fig1, ax1 = plt.subplots(figsize=(6.6, 4.0))
    pts = [(0.0, 0.0)] + list(waypoints)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax1.plot(xs, ys, linestyle='--', linewidth=1.5)
    ax1.scatter(xs, ys, marker='x', s=70)
    ax1.scatter([frame["x_km"]], [frame["y_km"]], s=100)
    if nav_estimated_path:
        ex = [p[0] for p in nav_estimated_path]
        ey = [p[1] for p in nav_estimated_path]
        ax1.plot(ex, ey, linewidth=1.0, alpha=0.8)
    circle = plt.Circle((0, 0), threat_zone_km, fill=False, alpha=0.7)
    ax1.add_patch(circle)
    ax1.set_title("Animated Mission Path (Frame View)")
    ax1.set_xlabel("X (km)")
    ax1.set_ylabel("Y (km)")
    ax1.set_aspect('equal', adjustable='box')
    st.pyplot(fig1, clear_figure=True)
    plt.close(fig1)

    # Detectability heatmap
    extent = max(5.0, threat_zone_km * 1.6, max([abs(p[0]) for p in pts] + [0]) + 2.0, max([abs(p[1]) for p in pts] + [0]) + 2.0)
    xs_h, ys_h, Z = compute_detectability_heatmap(extent, overall_score, visual_score, thermal_score, threat_zone_km)
    fig2, ax2 = plt.subplots(figsize=(6.6, 4.2))
    im = ax2.imshow(Z, origin='lower', extent=[xs_h.min(), xs_h.max(), ys_h.min(), ys_h.max()], aspect='auto')
    ax2.plot(xs, ys, linestyle='--', linewidth=1.0)
    ax2.scatter([frame["x_km"]], [frame["y_km"]], s=80)
    if nav_estimated_path:
        ex = [p[0] for p in nav_estimated_path]
        ey = [p[1] for p in nav_estimated_path]
        ax2.plot(ex, ey, linewidth=1.0, alpha=0.8)
    ax2.set_title("Detectability Heatmap")
    ax2.set_xlabel("X (km)")
    ax2.set_ylabel("Y (km)")
    plt.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
    st.pyplot(fig2, clear_figure=True)
    plt.close(fig2)

    # 3D path visualization
    fig3 = plt.figure(figsize=(6.6, 4.4))
    ax3 = fig3.add_subplot(111, projection='3d')
    z = [0.0] + [float(altitude_m) for _ in waypoints]
    ax3.plot(xs, ys, z, linewidth=1.4)
    ax3.scatter([frame["x_km"]], [frame["y_km"]], [float(frame["altitude_m"])], s=60)
    if nav_estimated_path:
        ex = [p[0] for p in nav_estimated_path]
        ey = [p[1] for p in nav_estimated_path]
        ez = [float(altitude_m)] * len(nav_estimated_path)
        ax3.plot(ex, ey, ez, linewidth=1.0, alpha=0.8)
    ax3.set_title("3D Mission Path")
    ax3.set_xlabel("X (km)")
    ax3.set_ylabel("Y (km)")
    ax3.set_zlabel("Altitude (m)")
    st.pyplot(fig3, clear_figure=True)
    plt.close(fig3)

    # Swarm movement if available
    if swarm_history:
        max_swarm_frame = max(0, len(swarm_history) - 1)
        swarm_frame_idx = min(frame_idx, max_swarm_frame)
        snapshot = swarm_history[swarm_frame_idx]
        fig4, ax4 = plt.subplots(figsize=(6.6, 4.0))
        ax4.plot(xs, ys, linestyle='--', linewidth=1.0)
        for s in snapshot:
            ax4.scatter([s.get("x_km", 0.0)], [s.get("y_km", 0.0)], s=80)
            ax4.text(s.get("x_km", 0.0) + 0.1, s.get("y_km", 0.0) + 0.1, s.get("id", "UAV"), fontsize=7)
        circle2 = plt.Circle((0, 0), threat_zone_km, fill=False, alpha=0.7)
        ax4.add_patch(circle2)
        ax4.set_title("Swarm Movement")
        ax4.set_xlabel("X (km)")
        ax4.set_ylabel("Y (km)")
        ax4.set_aspect('equal', adjustable='box')
        st.pyplot(fig4, clear_figure=True)
        plt.close(fig4)



def generate_tactical_briefing(
    llm_enabled: bool,
    tactical_mode_enabled: bool,
    params: Dict[str, Any],
) -> str:
    """Mission-aware briefing system. Uses LLM when available, heuristic fallback otherwise."""
    if not tactical_mode_enabled:
        return "Tactical Mode is disabled."

    heuristic_lines = []

    altitude = float(params.get("altitude_m", 0.0))
    speed = float(params.get("speed_kmh", 0.0))
    cloud = float(params.get("cloud_cover", 0.0))
    thermal = float(params.get("thermal_score", 0.0))
    visual = float(params.get("visual_score", 0.0))
    overall = float(params.get("overall_score", 0.0))
    endurance = float(params.get("endurance_min", 0.0))
    loiter_minutes = float(params.get("loiter_minutes", 0.0))
    rtb_required = bool(params.get("include_rtb", False))
    hybrid_possible = bool(params.get("hybrid_possible", False))
    autopilot_speed = float(params.get("autopilot_target_speed_kmh", speed))
    autopilot_alt = float(params.get("autopilot_target_altitude_m", altitude))
    detection_range = float(params.get("sensor_max_likely_detection_km", 0.0))
    terrain_mask = float(params.get("terrain_masking_score", 0.0))
    mission_feasible = bool(params.get("mission_feasible", True))
    radar_detect_probability_pct = float(params.get("radar_detect_probability_pct", 0.0))
    adversary_posture = str(params.get("adversary_posture", "Nominal"))
    allowed_loiter_min = float(params.get("allowed_loiter_min", loiter_minutes))

    if overall >= 70:
        heuristic_lines.append(
            f"Recommend ingress at approximately {int(max(100, autopilot_alt))} m AGL-equivalent with airspeed near {autopilot_speed:.0f} km/h to reduce exposure."
        )
    elif overall >= 50:
        heuristic_lines.append(
            f"Exposure is moderate. Hold a conservative ingress profile around {int(max(100, autopilot_alt))} m and avoid unnecessary speed spikes."
        )
    else:
        heuristic_lines.append(
            "Current exposure is relatively low. Mission profile is acceptable for controlled ingress under present conditions."
        )

    if hybrid_possible and thermal >= 60:
        heuristic_lines.append("Activate Hybrid Assist during ingress or threat-zone transit, not during extended cruise.")
    elif thermal >= 60:
        heuristic_lines.append("Thermal risk is elevated. Reduce prolonged climb or sustained high-power segments before target-area entry.")

    if loiter_minutes > 0:
        if radar_detect_probability_pct >= 60 or adversary_posture in ["Contested", "High-Threat"]:
            heuristic_lines.append(f"Radar threat penalizes loiter. Reduce on-station time to about {allowed_loiter_min:.0f} minutes or delay orbit entry.")
        elif cloud < 60 and visual >= 55:
            heuristic_lines.append("Delay loiter until cloud cover rises above roughly 60% or route masking improves.")
        elif not mission_feasible:
            heuristic_lines.append("Loiter request exceeds safe reserve margins. Reduce loiter duration before execution.")
        else:
            heuristic_lines.append(f"Loiter window appears supportable for about {loiter_minutes:.0f} minutes under current reserve constraints.")

    if detection_range >= 8.0:
        heuristic_lines.append(f"Likely sensor detection range is long ({detection_range:.1f} km). Favor terrain masking and non-linear routing on ingress.")
    elif detection_range >= 4.0:
        heuristic_lines.append(f"Likely sensor detection range is moderate ({detection_range:.1f} km). Use cloud cover and route shaping to manage exposure.")

    if terrain_mask >= 45:
        heuristic_lines.append("Terrain masking is strong enough to justify low-altitude shielded transit through exposed sectors.")
    elif terrain_mask <= 20:
        heuristic_lines.append("Terrain masking is weak. Do not assume terrain will break line-of-sight in the threat zone.")

    if rtb_required and not mission_feasible:
        heuristic_lines.append("Return-to-Base reserve is not secure. Reconfigure speed, loiter, or route before launch.")
    elif rtb_required:
        heuristic_lines.append("RTB reserve is protected. Maintain reserve discipline and avoid extending on-station time without reassessment.")

    heuristic_lines = heuristic_lines[:5]

    if not llm_enabled:
        return "\n".join([f"- {line}" for line in heuristic_lines])

    prompt = f"""
You are writing a concise tactical mission briefing for a UAV operator.
Return 4-6 short bullet points only.

Mission context:
- Platform: {params.get('drone', 'UAV')}
- Power system: {params.get('power_system', 'Unknown')}
- Flight mode: {params.get('flight_mode', 'Unknown')}
- Altitude: {altitude:.0f} m
- Speed: {speed:.1f} km/h
- Cloud cover: {cloud:.0f}%
- Detectability scores: visual {visual:.0f}/100, thermal {thermal:.0f}/100, overall {overall:.0f}/100
- Endurance: {endurance:.1f} min
- Loiter request: {loiter_minutes:.1f} min
- RTB required: {rtb_required}
- Hybrid possible: {hybrid_possible}
- Sensor likely detection range: {detection_range:.1f} km
- Terrain masking score: {terrain_mask:.1f}/100
- Mission feasible: {mission_feasible}
- Radar detection probability: {radar_detect_probability_pct:.1f}%
- Adversary posture: {adversary_posture}
- Allowed loiter after threat coupling: {allowed_loiter_min:.1f} min
- Recommended ingress profile from onboard logic: {autopilot_alt:.0f} m and {autopilot_speed:.0f} km/h

Write like an operator briefing, not generic advice.
Prefer mission-aware lines such as ingress profile, loiter timing, RTB caution, threat exposure, terrain masking, and hybrid-assist timing.
"""
    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise UAV tactical briefer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=220
        )
        content = resp.choices[0].message.content.strip()
        return content
    except Exception:
        return "\n".join([f"- {line}" for line in heuristic_lines])


def render_tactical_briefing_panel(briefing_text: str):
    st.markdown(
        "<div class='section-card'><div class='section-title'>LLM Tactical Mode</div>"
        "<div class='section-note'>Mission-aware briefing system for ingress, loiter timing, reserve posture, and exposure management.</div></div>",
        unsafe_allow_html=True,
    )
    st.write(briefing_text)





def compute_adversary_simulation(
    enabled: bool,
    radar_density: float,
    ir_density: float,
    jammer_density: float,
    altitude_m: int,
    speed_kmh: float,
    overall_detectability: float,
    visual_score: float,
    thermal_score: float,
    sensor_detection_range_km: float,
    terrain_masking_score: float,
    route_score: float,
    threat_zone_km: float,
    power_system: str,
    radar_frequency_ghz: float = 10.0,
    radar_tx_power_kw: float = 40.0,
    effective_size_m: float = 1.0,
) -> Dict[str, Any]:
    result = {
        "enabled": enabled,
        "active": False,
        "radar_risk": 0.0,
        "ir_tracker_risk": 0.0,
        "jammer_risk": 0.0,
        "combined_threat_score": 0.0,
        "survivability_score": 100.0,
        "recommended_posture": "Nominal",
        "radar_detection_probability_pct": 0.0,
        "rf_received_power_norm_db": 0.0,
        "actions": [],
    }
    if not enabled:
        return result

    import math
    c = 299792458.0
    lam = c / max(1e9, float(radar_frequency_ghz) * 1e9)
    range_m = max(500.0, float(threat_zone_km) * 1000.0)
    pt_w = max(1000.0, float(radar_tx_power_kw) * 1000.0)

    sigma_rcs = max(0.01, 0.08 * (max(0.2, float(effective_size_m)) ** 2) * (0.6 + 0.4 * overall_detectability / 100.0))
    g_lin = 1000.0
    pr_w = (pt_w * (g_lin ** 2) * (lam ** 2) * sigma_rcs) / max(1.0, ((4.0 * math.pi) ** 3) * (range_m ** 4))

    radar_mask_relief = max(0.0, min(1.0, terrain_masking_score / 100.0))
    radar_alt_factor = min(1.0, max(0.0, altitude_m / 1200.0))
    pr_w *= (1.0 - 0.55 * radar_mask_relief) * (0.75 + 0.25 * radar_alt_factor)

    jammer_factor = max(0.0, min(1.0, jammer_density))
    snr_proxy = pr_w / max(1e-12, 1e-9 * (1.0 + 8.0 * jammer_factor))
    rf_db = 10.0 * math.log10(max(1e-16, pr_w))

    p_det_radar = 1.0 / (1.0 + math.exp(-3.2 * (math.log10(max(1e-12, snr_proxy)) + 8.5)))
    p_det_radar *= (0.35 + 0.65 * radar_density)
    p_det_radar = max(0.0, min(1.0, p_det_radar))

    radar_risk = 100.0 * max(0.0, min(1.0,
        0.55 * p_det_radar +
        0.15 * radar_alt_factor +
        0.15 * (overall_detectability / 100.0) +
        0.10 * min(1.0, route_score / 100.0) -
        0.18 * radar_mask_relief
    ))

    ir_risk = 100.0 * max(0.0, min(1.0,
        0.40 * ir_density +
        0.35 * (thermal_score / 100.0) +
        0.15 * min(1.0, sensor_detection_range_km / max(1.0, threat_zone_km * 2.0)) +
        0.10 * max(0.0, min(1.0, speed_kmh / 180.0))
    ))
    if power_system == "ICE":
        ir_risk = min(100.0, ir_risk * 1.08)

    jammer_risk = 100.0 * max(0.0, min(1.0,
        0.55 * jammer_density +
        0.20 * min(1.0, sensor_detection_range_km / 10.0) +
        0.15 * min(1.0, route_score / 100.0) +
        0.10 * max(0.0, min(1.0, altitude_m / 1500.0))
    ))

    combined = 0.40 * radar_risk + 0.35 * ir_risk + 0.25 * jammer_risk
    survivability = max(0.0, 100.0 - combined)

    posture = "Nominal"
    if combined >= 75:
        posture = "High-Threat"
    elif combined >= 50:
        posture = "Contested"
    elif combined >= 30:
        posture = "Caution"

    actions = []
    if radar_risk >= 60:
        actions.append("Radar threat elevated — reduce altitude, exploit terrain masking, and avoid long exposed transits.")
    if p_det_radar >= 0.60:
        actions.append("Radar-equation estimate indicates high radar detection probability at the present threat range.")
    if ir_risk >= 60:
        actions.append("IR tracking threat elevated — cut sustained power, compress climb profile, and favor cloud or masking before loiter.")
    if jammer_risk >= 60:
        actions.append("Jammer threat elevated — shorten exposed control windows and prioritize relay / resilient swarm posture.")
    if combined >= 70:
        actions.append("Combined adversary threat is high — recommend delayed ingress or route revision before execution.")
    elif combined >= 45:
        actions.append("Mission area is contested — maintain reserve discipline and avoid unnecessary on-station time.")
    else:
        actions.append("Threat environment is manageable under current profile, but continue monitoring radar / IR / jammer overlap.")

    result.update({
        "active": True,
        "radar_risk": round(radar_risk, 1),
        "ir_tracker_risk": round(ir_risk, 1),
        "jammer_risk": round(jammer_risk, 1),
        "combined_threat_score": round(combined, 1),
        "survivability_score": round(survivability, 1),
        "recommended_posture": posture,
        "radar_detection_probability_pct": round(100.0 * p_det_radar, 1),
        "rf_received_power_norm_db": round(rf_db, 2),
        "actions": actions,
    })
    return result


def render_adversary_simulation_panel(adversary_profile: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Adversary Simulation</div>"
        "<div class='section-note'>Planning-grade hostile-environment model for radar zones, IR tracking systems, and jammers.</div></div>",
        unsafe_allow_html=True,
    )
    if not adversary_profile.get("enabled", False):
        st.info("Adversary Simulation is disabled.")
        return

    posture = adversary_profile.get("recommended_posture", "Nominal")
    if posture == "High-Threat":
        st.error(f"Threat posture: {posture}")
    elif posture in ["Contested", "Caution"]:
        st.warning(f"Threat posture: {posture}")
    else:
        st.success(f"Threat posture: {posture}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Radar Risk", f"{adversary_profile.get('radar_risk', 0.0):.1f}/100")
    with c2:
        st.metric("IR Tracker Risk", f"{adversary_profile.get('ir_tracker_risk', 0.0):.1f}/100")
    with c3:
        st.metric("Jammer Risk", f"{adversary_profile.get('jammer_risk', 0.0):.1f}/100")

    c4, c5, c6, c7 = st.columns(4)
    with c4:
        st.metric("Combined Threat", f"{adversary_profile.get('combined_threat_score', 0.0):.1f}/100")
    with c5:
        st.metric("Survivability", f"{adversary_profile.get('survivability_score', 100.0):.1f}/100")
    with c6:
        st.metric("Radar Detect Prob", f"{adversary_profile.get('radar_detection_probability_pct', 0.0):.1f}%")
    with c7:
        st.metric("RF Rx Power", f"{adversary_profile.get('rf_received_power_norm_db', 0.0):.2f} dB")

    for action in adversary_profile.get("actions", []):
        if "high" in action.lower() or "elevated" in action.lower():
            st.warning(action)
        else:
            st.info(action)



def compute_gnss_denied_navigation(
    enabled: bool,
    fusion_quality: float,
    drift_sensitivity: float,
    map_uncertainty_factor: float,
    flight_time_minutes: float,
    total_distance_km: float,
    speed_kmh: float,
    terrain_masking_score: float,
    jammer_risk: float,
    route_score: float,
) -> Dict[str, Any]:
    """Planning-grade GNSS-denied navigation model.
    Approximates fused-nav health, drift growth, and map uncertainty under degraded navigation.
    """
    result = {
        "enabled": enabled,
        "active": False,
        "fusion_health_score": 100.0,
        "estimated_drift_km": 0.0,
        "map_uncertainty_km": 0.0,
        "navigation_confidence": 100.0,
        "recommended_mode": "Nominal",
        "actions": [],
    }
    if not enabled:
        return result

    # More jamming and route complexity hurt dead-reckoning / fused-nav health.
    jammer_factor = max(0.0, min(1.0, jammer_risk / 100.0))
    route_factor = max(0.0, min(1.0, route_score / 100.0))
    masking_bonus = max(0.0, min(1.0, terrain_masking_score / 100.0))

    fusion_health = 100.0 * max(0.0, min(1.0,
        0.75 * (fusion_quality / 1.5) +
        0.10 * masking_bonus +
        0.15 * (1.0 - jammer_factor)
    ))

    # Drift grows with time, speed, and degraded fusion.
    drift_rate_km_per_hr = 0.08 * drift_sensitivity * (1.0 + 1.8 * jammer_factor + 0.6 * route_factor) * (1.15 - 0.4 * (fusion_quality / 1.5))
    estimated_drift_km = max(0.0, drift_rate_km_per_hr * (flight_time_minutes / 60.0))

    # Map uncertainty compounds route length and base uncertainty factor.
    map_uncertainty_km = max(0.0, (0.03 * total_distance_km + 0.35 * map_uncertainty_factor) * (1.0 + 0.8 * jammer_factor))

    nav_conf = max(0.0, 100.0 - (30.0 * estimated_drift_km + 40.0 * map_uncertainty_km))
    nav_conf = min(nav_conf, fusion_health)

    mode = "Nominal"
    if nav_conf < 40:
        mode = "Degraded"
    elif nav_conf < 65:
        mode = "Caution"

    actions = []
    if fusion_health < 60:
        actions.append("Sensor-fusion health is degraded — shorten exposed legs and reduce dependence on precise waypoint timing.")
    else:
        actions.append("Sensor-fusion health is acceptable for planning-grade GNSS-denied navigation.")

    if estimated_drift_km >= 1.0:
        actions.append("Estimated drift is high — tighten waypoint spacing or reduce mission duration before GNSS-denied ingress.")
    elif estimated_drift_km >= 0.4:
        actions.append("Estimated drift is moderate — maintain conservative routing and avoid extended low-feature terrain.")

    if map_uncertainty_km >= 0.8:
        actions.append("Map uncertainty is significant — confirm terrain / landmark assumptions before relying on masked routing.")
    elif map_uncertainty_km >= 0.3:
        actions.append("Map uncertainty is present — use broader reserve margins for off-nominal navigation.")

    if jammer_factor >= 0.6:
        actions.append("Jammer pressure is high — prioritize resilient swarm relay or shorter GNSS-denied segments.")

    if nav_conf < 40:
        actions.append("Navigation confidence is low — recommend abort / simplify route under GNSS-denied conditions.")
    elif nav_conf < 65:
        actions.append("Navigation confidence is moderate — favor shorter legs and stronger sensor-fusion posture.")
    else:
        actions.append("Navigation confidence is strong enough for planning-grade degraded-navigation assessment.")

    result.update({
        "active": True,
        "fusion_health_score": round(fusion_health, 1),
        "estimated_drift_km": round(estimated_drift_km, 3),
        "map_uncertainty_km": round(map_uncertainty_km, 3),
        "navigation_confidence": round(nav_conf, 1),
        "recommended_mode": mode,
        "actions": actions[:5],
    })
    return result


def render_gnss_denied_navigation_panel(nav_profile: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>GNSS-Denied Navigation</div>"
        "<div class='section-note'>Planning-grade degraded-navigation estimate covering sensor fusion, drift growth, and map uncertainty.</div></div>",
        unsafe_allow_html=True,
    )
    if not nav_profile.get("enabled", False):
        st.info("GNSS-Denied Navigation is disabled.")
        return

    mode = nav_profile.get("recommended_mode", "Nominal")
    if mode == "Degraded":
        st.error(f"Navigation mode: {mode}")
    elif mode == "Caution":
        st.warning(f"Navigation mode: {mode}")
    else:
        st.success(f"Navigation mode: {mode}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Fusion Health", f"{nav_profile.get('fusion_health_score', 100.0):.1f}/100")
    with c2:
        st.metric("Estimated Drift", f"{nav_profile.get('estimated_drift_km', 0.0):.3f} km")
    with c3:
        st.metric("Map Uncertainty", f"{nav_profile.get('map_uncertainty_km', 0.0):.3f} km")

    c4 = st.columns(1)[0]
    with c4:
        st.metric("Navigation Confidence", f"{nav_profile.get('navigation_confidence', 100.0):.1f}/100")

    for action in nav_profile.get("actions", []):
        if "abort" in action.lower() or "degraded" in action.lower() or "high" in action.lower():
            st.warning(action)
        else:
            st.info(action)




def estimate_available_shaft_power_W(profile: Dict[str, Any], total_mass_kg: float, battery_capacity_wh: float = 0.0) -> float:
    # Planning-grade available shaft-power estimate.
    # Fixed-wing ICE uses nominal engine power; battery aircraft use a mass-scaled electric ceiling.
    if profile.get("power_system") == "ICE":
        return max(1500.0, 1000.0 * estimate_engine_nominal_power_kw(profile))
    if profile.get("type") == "fixed":
        profile_cap = float(profile.get("max_shaft_power_W", 0.0))
        if profile_cap > 0:
            return profile_cap
        # conservative battery/electric estimate for small fixed-wing UAVs
        return max(300.0, min(12000.0, 700.0 + 550.0 * total_mass_kg + 0.10 * float(profile.get("battery_wh", battery_capacity_wh or 0.0))))
    # rotorcraft placeholder retained as proxy
    return max(500.0, 800.0 * total_mass_kg)


def compute_power_available_envelope(
    profile: Dict[str, Any],
    total_mass_kg: float,
    altitude_m: int,
    flight_speed_kmh: float,
    rho: float,
) -> Dict[str, float]:
    # Power-available / excess-power climb and service-ceiling estimate for fixed-wing aircraft.
    # Rotorcraft fall back to proxy values elsewhere.
    if profile.get("type") != "fixed":
        return {"power_available_W": 0.0, "power_required_W": 0.0, "excess_power_W": 0.0, "roc_mps": 0.0, "service_ceiling_m": 0.0}

    weight_N = total_mass_kg * G0
    V_ms = max(8.0, float(flight_speed_kmh) / 3.6)
    perf = fixedwing_power_required(
        weight_N=weight_N,
        rho=rho,
        V_ms=V_ms,
        wing_area_m2=float(profile.get("wing_area_m2", 0.6)),
        span_m=float(profile.get("wingspan_m", 2.0)),
        cd0=float(profile.get("cd0", 0.05)),
        e=float(profile.get("oswald_e", 0.75)),
        prop_eff=float(profile.get("prop_eff", 0.70)),
        power_system=profile.get("power_system", "Battery"),
        hotel_W=float(profile.get("hotel_W", HOTEL_W_DEFAULT)),
        install_frac=0.10,
        cl_max=float(profile.get("cl_max", 1.4)),
    )
    p_req = float(perf["total_W"])

    p_avail_sl = estimate_available_shaft_power_W(profile, total_mass_kg, float(profile.get("battery_wh", 0.0)))
    # power available degrades with density; exponent softened to remain planning-grade
    sigma = max(0.15, min(1.2, rho / RHO0))
    if profile.get("power_system") == "ICE":
        p_avail = p_avail_sl * sigma ** 0.85
    else:
        p_avail = p_avail_sl * sigma ** 0.65

    excess_power_W = p_avail - p_req
    roc_mps = max(0.0, excess_power_W / max(1.0, weight_N))

    # Solve service ceiling where ROC falls to 0.5 m/s by scanning ISA density
    service_ceiling_m = float(altitude_m)
    target_roc = 0.5
    for h in range(0, 18001, 250):
        rho_h = isa_density(h, T0_STD + 15.0)  # standard-ish reference temperature
        sigma_h = max(0.12, min(1.2, rho_h / RHO0))
        if profile.get("power_system") == "ICE":
            p_av_h = p_avail_sl * sigma_h ** 0.85
        else:
            p_av_h = p_avail_sl * sigma_h ** 0.65

        perf_h = fixedwing_power_required(
            weight_N=weight_N,
            rho=rho_h,
            V_ms=V_ms,
            wing_area_m2=float(profile.get("wing_area_m2", 0.6)),
            span_m=float(profile.get("wingspan_m", 2.0)),
            cd0=float(profile.get("cd0", 0.05)),
            e=float(profile.get("oswald_e", 0.75)),
            prop_eff=float(profile.get("prop_eff", 0.70)),
            power_system=profile.get("power_system", "Battery"),
            hotel_W=float(profile.get("hotel_W", HOTEL_W_DEFAULT)),
            install_frac=0.10,
            cl_max=float(profile.get("cl_max", 1.4)),
        )
        roc_h = max(0.0, (p_av_h - float(perf_h["total_W"])) / max(1.0, weight_N))
        if roc_h < target_roc:
            service_ceiling_m = float(h)
            break
        service_ceiling_m = float(h)

    return {
        "power_available_W": round(p_avail, 2),
        "power_required_W": round(p_req, 2),
        "excess_power_W": round(excess_power_W, 2),
        "roc_mps": round(roc_mps, 3),
        "service_ceiling_m": round(service_ceiling_m, 1),
    }


def compute_flight_envelope_enforcement(
    enabled: bool,
    profile: Dict[str, Any],
    total_mass_kg: float,
    altitude_m: int,
    flight_speed_kmh: float,
    elevation_gain_m: int,
    rho: float,
) -> Dict[str, Any]:
    # Flight envelope checks with power-available climb and service ceiling for fixed-wing aircraft.
    g = G0
    weight_N = total_mass_kg * g
    platform_type = profile.get("type", "fixed")

    result = {
        "enabled": enabled,
        "active": False,
        "stall_speed_kmh": 0.0,
        "recommended_min_speed_kmh": 0.0,
        "max_climb_rate_mps": 0.0,
        "requested_climb_rate_mps": 0.0,
        "service_ceiling_m": 0.0,
        "power_available_W": 0.0,
        "power_required_W": 0.0,
        "excess_power_W": 0.0,
        "speed_violation": False,
        "climb_violation": False,
        "ceiling_violation": False,
        "adjusted_speed_kmh": float(flight_speed_kmh),
        "adjusted_altitude_m": int(altitude_m),
        "actions": [],
    }
    if not enabled:
        return result

    if platform_type == "fixed":
        wing_area = float(profile.get("wing_area_m2", 0.6))
        cl_max = float(profile.get("cl_max", 1.4))
        stall_speed_ms = ((2.0 * weight_N) / max(1e-6, rho * wing_area * cl_max)) ** 0.5
        stall_speed_kmh = stall_speed_ms * 3.6
        recommended_min_speed_kmh = 1.20 * stall_speed_kmh

        power_env = compute_power_available_envelope(
            profile=profile,
            total_mass_kg=total_mass_kg,
            altitude_m=altitude_m,
            flight_speed_kmh=max(float(flight_speed_kmh), recommended_min_speed_kmh),
            rho=rho,
        )
        max_climb_rate_mps = float(power_env["roc_mps"])
        service_ceiling_m = float(power_env["service_ceiling_m"])
        p_av = float(power_env["power_available_W"])
        p_req = float(power_env["power_required_W"])
        p_excess = float(power_env["excess_power_W"])
    else:
        stall_speed_kmh = 0.0
        recommended_min_speed_kmh = 0.0
        if total_mass_kg > 20:
            max_climb_rate_mps = 5.0
            service_ceiling_m = 5000.0
        elif total_mass_kg > 5:
            max_climb_rate_mps = 4.0
            service_ceiling_m = 3500.0
        else:
            max_climb_rate_mps = 3.0
            service_ceiling_m = 2500.0
        p_av = 0.0
        p_req = 0.0
        p_excess = 0.0

    requested_climb_rate_mps = max(0.0, float(elevation_gain_m) / 60.0)

    speed_violation = False
    adjusted_speed = float(flight_speed_kmh)
    if platform_type == "fixed" and flight_speed_kmh < recommended_min_speed_kmh:
        speed_violation = True
        adjusted_speed = recommended_min_speed_kmh

    climb_violation = requested_climb_rate_mps > max_climb_rate_mps
    ceiling_violation = float(altitude_m) > service_ceiling_m
    adjusted_altitude = int(min(float(altitude_m), service_ceiling_m))

    actions = []
    if speed_violation:
        actions.append(f"Speed below recommended fixed-wing minimum; raise airspeed to at least {recommended_min_speed_kmh:.1f} km/h.")
    if climb_violation:
        actions.append(f"Requested climb rate exceeds power-available capability; limit climb to about {max_climb_rate_mps:.1f} m/s.")
    if ceiling_violation:
        actions.append(f"Requested altitude exceeds power-limited service ceiling; cap altitude near {service_ceiling_m:.0f} m.")
    if platform_type == "fixed":
        actions.append(f"Power available {p_av:.0f} W vs power required {p_req:.0f} W gives excess power {p_excess:.0f} W.")
    if not (speed_violation or climb_violation or ceiling_violation):
        actions.append("Requested mission profile remains inside the planning-grade flight envelope.")

    result.update({
        "active": True,
        "stall_speed_kmh": round(stall_speed_kmh, 2),
        "recommended_min_speed_kmh": round(recommended_min_speed_kmh, 2),
        "max_climb_rate_mps": round(max_climb_rate_mps, 2),
        "requested_climb_rate_mps": round(requested_climb_rate_mps, 2),
        "service_ceiling_m": round(service_ceiling_m, 1),
        "power_available_W": round(p_av, 2),
        "power_required_W": round(p_req, 2),
        "excess_power_W": round(p_excess, 2),
        "speed_violation": bool(speed_violation),
        "climb_violation": bool(climb_violation),
        "ceiling_violation": bool(ceiling_violation),
        "adjusted_speed_kmh": round(adjusted_speed, 2),
        "adjusted_altitude_m": int(adjusted_altitude),
        "actions": actions,
    })
    return result


def render_flight_envelope_panel(env_profile: Dict[str, Any], platform_type: str):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Flight Envelope Enforcement</div>"
        "<div class='section-note'>Planning-grade checks for stall speed, climb-rate limits, and service ceiling to prevent unrealistic mission configurations.</div></div>",
        unsafe_allow_html=True,
    )
    if not env_profile.get("enabled", False):
        st.info("Flight Envelope Enforcement is disabled.")
        return

    if env_profile.get("speed_violation", False) or env_profile.get("climb_violation", False) or env_profile.get("ceiling_violation", False):
        st.warning("Envelope status: LIMIT EXCEEDED")
    else:
        st.success("Envelope status: WITHIN LIMITS")

    cols = st.columns(3)
    if platform_type == "fixed":
        with cols[0]:
            st.metric("Stall Speed", f"{env_profile.get('stall_speed_kmh', 0.0):.1f} km/h")
        with cols[1]:
            st.metric("Recommended Min Speed", f"{env_profile.get('recommended_min_speed_kmh', 0.0):.1f} km/h")
        with cols[2]:
            st.metric("Service Ceiling", f"{env_profile.get('service_ceiling_m', 0.0):.0f} m")
    else:
        with cols[0]:
            st.metric("Max Climb Rate", f"{env_profile.get('max_climb_rate_mps', 0.0):.1f} m/s")
        with cols[1]:
            st.metric("Service Ceiling", f"{env_profile.get('service_ceiling_m', 0.0):.0f} m")
        with cols[2]:
            st.metric("Requested Climb Rate", f"{env_profile.get('requested_climb_rate_mps', 0.0):.1f} m/s")

    if platform_type == "fixed":
        cols2 = st.columns(4)
        with cols2[0]:
            st.metric("Requested Climb Rate", f"{env_profile.get('requested_climb_rate_mps', 0.0):.1f} m/s")
        with cols2[1]:
            st.metric("Max Climb Rate", f"{env_profile.get('max_climb_rate_mps', 0.0):.1f} m/s")
        with cols2[2]:
            st.metric("Power Available", f"{env_profile.get('power_available_W', 0.0):.0f} W")
        with cols2[3]:
            st.metric("Excess Power", f"{env_profile.get('excess_power_W', 0.0):.0f} W")

    for action in env_profile.get("actions", []):
        if "exceeds" in action.lower() or "below" in action.lower() or "cap altitude" in action.lower():
            st.warning(action)
        else:
            st.info(action)




def compute_battery_temp_discharge_factor(temp_c: float) -> float:
    # Planning-grade temperature discharge multiplier / OCV availability proxy
    t = float(temp_c)
    if t <= -10:
        return 0.58
    if t <= 0:
        return 0.68
    if t <= 10:
        return 0.80
    if t <= 20:
        return 0.92
    if t <= 30:
        return 1.00
    if t <= 40:
        return 0.96
    if t <= 50:
        return 0.90
    return 0.82


def estimate_engine_nominal_power_kw(profile: Dict[str, Any]) -> float:
    name = str(profile.get('name', '')) or str(profile)
    if 'MQ-9' in name:
        return 670.0
    if 'MQ-1' in name:
        return 86.0
    if profile.get('power_system') == 'ICE':
        return 120.0
    return 0.0


def compute_bsfc_map_gpkwh(throttle_ratio: float, wear_factor: float) -> float:
    # Planning-grade BSFC map with best efficiency near cruise-mid throttle
    x = max(0.15, min(1.20, float(throttle_ratio)))
    # U-shaped curve: lower BSFC is better
    bsfc = 255.0 + 120.0 * ((x - 0.72) ** 2) / 0.25
    bsfc *= (2.0 - max(0.80, min(1.20, float(wear_factor))))  # wear <1 raises BSFC
    return max(240.0, min(420.0, bsfc))


def compute_battery_ecm(
    usable_capacity_wh: float,
    nominal_voltage_v: float,
    internal_resistance_ohm: float,
    load_power_w: float,
    temp_factor: float,
) -> Dict[str, float]:
    # 1-R equivalent-circuit surrogate
    v_oc = max(8.0, float(nominal_voltage_v) * max(0.70, min(1.05, temp_factor)))
    current_a = max(0.0, float(load_power_w) / max(1e-6, v_oc))
    v_loaded = max(0.0, v_oc - current_a * float(internal_resistance_ohm))
    i2r_loss_w = (current_a ** 2) * float(internal_resistance_ohm)
    # Use loaded/OCV ratio as an availability reduction on remaining usable energy
    voltage_eff = max(0.60, min(1.0, v_loaded / max(1e-6, v_oc)))
    effective_capacity_wh = max(0.0, float(usable_capacity_wh) * voltage_eff)
    return {
        'ocv_v': round(v_oc, 3),
        'loaded_v': round(v_loaded, 3),
        'current_a': round(current_a, 3),
        'internal_loss_w': round(i2r_loss_w, 3),
        'voltage_efficiency': round(voltage_eff, 3),
        'effective_capacity_wh': round(effective_capacity_wh, 3),
    }


def compute_degradation_model(
    enabled: bool,
    profile: Dict[str, Any],
    battery_cycle_count: int,
    temperature_c: float,
    battery_capacity_wh: float,
    battery_nominal_voltage_v: float,
    battery_internal_resistance_mohm: float,
    total_draw_W: float,
    total_power_W: float,
    engine_wear_factor: float,
) -> Dict[str, Any]:
    # Planning-grade degradation model upgraded toward MIT-style expectations:
    # battery equivalent-circuit surrogate + BSFC-map-style ICE efficiency model
    result = {
        "enabled": enabled,
        "active": False,
        "battery_cycle_factor": 1.0,
        "battery_temp_factor": 1.0,
        "battery_degraded_capacity_wh": float(battery_capacity_wh),
        "battery_health_score": 100.0,
        "battery_ocv_v": 0.0,
        "battery_loaded_v": 0.0,
        "battery_current_a": 0.0,
        "battery_internal_loss_w": 0.0,
        "battery_voltage_efficiency": 1.0,
        "ice_throttle_ratio": 0.0,
        "ice_efficiency_factor": 1.0,
        "ice_effective_power_kw": 0.0,
        "ice_bsfc_gpkwh": 0.0,
        "recommended_posture": "Nominal",
        "actions": [],
    }
    if not enabled:
        return result

    power_system = profile.get("power_system", "Battery")
    actions = []

    cycle_count = max(0, int(battery_cycle_count))
    cycle_factor = max(0.70, 1.0 - 0.00018 * cycle_count - 0.00000012 * (cycle_count ** 2))
    temp_factor = compute_battery_temp_discharge_factor(temperature_c)
    usable_capacity_wh = max(0.0, float(battery_capacity_wh) * cycle_factor * temp_factor)

    battery_health_score = max(0.0, min(100.0, 100.0 * cycle_factor))
    ecm = compute_battery_ecm(
        usable_capacity_wh=usable_capacity_wh,
        nominal_voltage_v=float(battery_nominal_voltage_v),
        internal_resistance_ohm=max(0.001, float(battery_internal_resistance_mohm) / 1000.0),
        load_power_w=float(total_draw_W),
        temp_factor=temp_factor,
    )

    if power_system == "Battery":
        if cycle_factor < 0.90:
            actions.append("Battery aging is reducing usable pack energy; monitor reserve margins more aggressively.")
        if temp_factor < 0.90:
            actions.append("Temperature-dependent discharge losses are active; expect reduced effective endurance.")
        if ecm["internal_loss_w"] > 0.05 * max(1.0, float(total_draw_W)):
            actions.append("Internal resistance losses are significant under the current load; expect voltage sag and lower effective capacity.")
        actions.append(f"Equivalent-circuit estimate: loaded voltage about {ecm['loaded_v']:.1f} V and internal loss about {ecm['internal_loss_w']:.1f} W.")

    nominal_kw = estimate_engine_nominal_power_kw(profile)
    ice_throttle_ratio = 0.0
    ice_eff_factor = 1.0
    ice_effective_power_kw = 0.0
    ice_bsfc = 0.0
    if power_system == "ICE":
        demanded_kw = max(0.0, float(total_power_W) / 1000.0)
        ice_throttle_ratio = demanded_kw / max(1.0, nominal_kw)
        ice_bsfc = compute_bsfc_map_gpkwh(ice_throttle_ratio, engine_wear_factor)
        # Convert lower BSFC to better efficiency factor around 255 g/kWh best case
        ice_eff_factor = max(0.55, min(1.0, 255.0 / max(1e-6, ice_bsfc)))
        ice_effective_power_kw = demanded_kw / max(0.55, ice_eff_factor)

        if ice_throttle_ratio > 0.85:
            actions.append("ICE throttle demand is high; BSFC is rising in the upper-throttle region.")
        elif ice_throttle_ratio < 0.35:
            actions.append("ICE is operating at low throttle where BSFC is typically weaker.")
        else:
            actions.append("ICE throttle setting is near the efficient cruise regime.")
        if engine_wear_factor < 0.95:
            actions.append("Engine wear factor indicates degraded propulsion efficiency; preserve extra fuel reserve.")
        actions.append(f"BSFC-map estimate: about {ice_bsfc:.0f} g/kWh at the current throttle condition.")

    posture = "Nominal"
    if power_system == "Battery" and (cycle_factor < 0.85 or temp_factor < 0.80 or ecm["voltage_efficiency"] < 0.82):
        posture = "Degraded"
    elif power_system == "Battery" and (cycle_factor < 0.92 or temp_factor < 0.92 or ecm["voltage_efficiency"] < 0.92):
        posture = "Caution"
    elif power_system == "ICE" and (ice_throttle_ratio > 0.90 or engine_wear_factor < 0.90 or ice_bsfc > 340.0):
        posture = "Degraded"
    elif power_system == "ICE" and (ice_throttle_ratio > 0.75 or engine_wear_factor < 0.98 or ice_bsfc > 300.0):
        posture = "Caution"

    if posture == "Degraded":
        actions.append("Degradation posture is degraded; shorten mission profile or increase reserve margin before execution.")
    elif posture == "Caution":
        actions.append("Degradation posture is cautionary; validate endurance and RTB margins against degraded performance.")
    else:
        actions.append("Degradation posture is nominal for planning purposes.")

    result.update({
        "active": True,
        "battery_cycle_factor": round(cycle_factor, 3),
        "battery_temp_factor": round(temp_factor, 3),
        "battery_degraded_capacity_wh": round(ecm['effective_capacity_wh'], 2),
        "battery_health_score": round(battery_health_score, 1),
        "battery_ocv_v": round(ecm['ocv_v'], 3),
        "battery_loaded_v": round(ecm['loaded_v'], 3),
        "battery_current_a": round(ecm['current_a'], 3),
        "battery_internal_loss_w": round(ecm['internal_loss_w'], 3),
        "battery_voltage_efficiency": round(ecm['voltage_efficiency'], 3),
        "ice_throttle_ratio": round(ice_throttle_ratio, 3),
        "ice_efficiency_factor": round(ice_eff_factor, 3),
        "ice_effective_power_kw": round(ice_effective_power_kw, 3),
        "ice_bsfc_gpkwh": round(ice_bsfc, 2),
        "recommended_posture": posture,
        "actions": actions[:6],
    })
    return result


def render_degradation_panel(deg_profile: Dict[str, Any], power_system: str):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Battery + Fuel Degradation Modeling</div>"
        "<div class='section-note'>Planning-grade battery aging, temperature discharge behavior, and ICE efficiency vs throttle.</div></div>",
        unsafe_allow_html=True,
    )
    if not deg_profile.get("enabled", False):
        st.info("Battery + Fuel Degradation Modeling is disabled.")
        return

    posture = deg_profile.get("recommended_posture", "Nominal")
    if posture == "Degraded":
        st.error(f"Degradation posture: {posture}")
    elif posture == "Caution":
        st.warning(f"Degradation posture: {posture}")
    else:
        st.success(f"Degradation posture: {posture}")

    if power_system == "Battery":
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Battery Health", f"{deg_profile.get('battery_health_score', 100.0):.1f}/100")
        with c2:
            st.metric("Cycle Factor", f"{deg_profile.get('battery_cycle_factor', 1.0):.3f}")
        with c3:
            st.metric("Temp Factor", f"{deg_profile.get('battery_temp_factor', 1.0):.3f}")

        c4, c5 = st.columns(2)
        with c4:
            st.metric("Loaded Voltage", f"{deg_profile.get('battery_loaded_v', 0.0):.2f} V")
        with c5:
            st.metric("Internal Loss", f"{deg_profile.get('battery_internal_loss_w', 0.0):.1f} W")
        st.metric("Degraded Capacity", f"{deg_profile.get('battery_degraded_capacity_wh', 0.0):.1f} Wh")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Throttle Ratio", f"{deg_profile.get('ice_throttle_ratio', 0.0):.2f}")
        with c2:
            st.metric("ICE Efficiency Factor", f"{deg_profile.get('ice_efficiency_factor', 1.0):.3f}")
        with c3:
            st.metric("Effective Power", f"{deg_profile.get('ice_effective_power_kw', 0.0):.2f} kW")
        st.metric("BSFC Map Value", f"{deg_profile.get('ice_bsfc_gpkwh', 0.0):.0f} g/kWh")

    for action in deg_profile.get("actions", []):
        if "degraded" in action.lower() or "high" in action.lower() or "reduced" in action.lower():
            st.warning(action)
        else:
            st.info(action)




def build_scenario_variants(
    base_inputs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    base = dict(base_inputs)
    nominal = dict(base); nominal["label"] = "Scenario A — Nominal"
    conservative = dict(base); conservative["label"] = "Scenario B — Conservative"; conservative["flight_speed_kmh"] = max(20.0, float(base["flight_speed_kmh"]) * 0.90); conservative["altitude_m"] = int(float(base["altitude_m"]) + 100); conservative["loiter_minutes"] = max(0.0, float(base["loiter_minutes"]) * 0.75)
    aggressive = dict(base); aggressive["label"] = "Scenario C — Aggressive"; aggressive["flight_speed_kmh"] = float(base["flight_speed_kmh"]) * 1.10; aggressive["altitude_m"] = max(0, int(float(base["altitude_m"]) - 100)); aggressive["loiter_minutes"] = float(base["loiter_minutes"]) * 1.25
    return [nominal, conservative, aggressive]


def evaluate_full_stack_scenario(
    profile: Dict[str, Any],
    scenario: Dict[str, Any],
) -> Dict[str, Any]:
    # Full-stack planning rerun through the major mission-support modules
    payload_weight_g = int(scenario["payload_weight_g"])
    flight_speed_kmh = float(scenario["flight_speed_kmh"])
    wind_speed_kmh = float(scenario["wind_speed_kmh"])
    temperature_c = float(scenario["temperature_c"])
    altitude_m = int(scenario["altitude_m"])
    elevation_gain_m = int(scenario["elevation_gain_m"])
    flight_mode = scenario["flight_mode"]
    gustiness = int(scenario["gustiness"])
    terrain_penalty = float(scenario["terrain_penalty"])
    stealth_drag_penalty = float(scenario["stealth_drag_penalty"])
    battery_capacity_wh = float(scenario.get("battery_capacity_wh", 0.0))
    fuel_tank_l = float(scenario.get("fuel_tank_l", 0.0))
    cloud_cover = int(scenario["cloud_cover"])
    humidity_factor = float(scenario["humidity_factor"])
    background_complexity = float(scenario["background_complexity"])
    effective_size_m = float(scenario["effective_size_m"])
    waypoints = list(scenario["waypoints"])
    loiter_minutes = float(scenario["loiter_minutes"])
    include_rtb = bool(scenario["include_rtb"])
    threat_zone_km = float(scenario["threat_zone_km"])
    sensor_band = scenario["sensor_band"]
    sensor_quality = float(scenario["sensor_quality"])

    if profile["power_system"] == "Battery":
        result = simulate_battery_aircraft(profile, payload_weight_g, flight_speed_kmh, wind_speed_kmh, temperature_c, altitude_m, elevation_gain_m, flight_mode, gustiness, terrain_penalty, stealth_drag_penalty, battery_capacity_wh)
    else:
        result = simulate_ice_aircraft(profile, payload_weight_g, flight_speed_kmh, wind_speed_kmh, temperature_c, altitude_m, elevation_gain_m, flight_mode, gustiness, terrain_penalty, stealth_drag_penalty, fuel_tank_l)

    rho = result["rho"]
    total_weight_kg = result["total_mass_kg"]
    flight_time_minutes = result["dispatch_endurance_min"]
    delta_T = result["thermal_load_deltaT_estimate_C"]
    detect = compute_detectability_scores_v3(delta_T, altitude_m, flight_speed_kmh, cloud_cover, gustiness, stealth_drag_penalty, profile["type"], profile["power_system"], effective_size_m, background_complexity, humidity_factor)
    visual_score = detect["visual_score"]; thermal_score = detect["thermal_score"]; overall_score = detect["overall_score"]; detect_confidence = detect["confidence"]

    autopilot_profile = run_detectability_autopilot(
        enabled=True,
        overall_score=overall_score, visual_score=visual_score, thermal_score=thermal_score,
        confidence=detect_confidence, altitude_m=altitude_m, speed_kmh=flight_speed_kmh,
        power_system=profile["power_system"], hybrid_assist_enabled=(profile["power_system"] == "ICE"),
        stealth_drag_penalty=stealth_drag_penalty,
    )
    route_optimization_profile = optimize_route_profile(
        enabled=True, waypoints=waypoints,
        speed_kmh=float(autopilot_profile.get("target_speed_kmh", flight_speed_kmh)),
        altitude_m=int(autopilot_profile.get("target_altitude_m", altitude_m)),
        overall_detectability=overall_score, visual_detectability=visual_score, thermal_detectability=thermal_score,
        terrain_penalty=terrain_penalty, stealth_drag_penalty=stealth_drag_penalty, threat_zone_km=threat_zone_km,
        radar_threat_penalty=0.0,
    )
    terrain_masking_profile = estimate_terrain_masking(
        enabled=True, waypoints=waypoints,
        altitude_m=int(route_optimization_profile.get("recommended_altitude_m", altitude_m)),
        terrain_penalty=terrain_penalty, cloud_cover=cloud_cover,
        overall_detectability=overall_score, visual_detectability=visual_score, thermal_detectability=thermal_score,
        threat_zone_km=threat_zone_km,
        terrain_ridge_amplitude_m=float(scenario.get('terrain_ridge_amplitude_m', 80.0)),
    )
    sensor_model_profile = compute_sensor_model(
        enabled=True, sensor_band=sensor_band, sensor_quality=sensor_quality,
        humidity_factor=humidity_factor, cloud_cover=cloud_cover,
        altitude_m=int(route_optimization_profile.get("recommended_altitude_m", altitude_m)),
        visual_score=visual_score, thermal_score=thermal_score, overall_score=overall_score, delta_t=delta_T,
    )
    adversary_profile = compute_adversary_simulation(
        enabled=True,
        radar_density=float(scenario["adversary_radar_density"]),
        ir_density=float(scenario["adversary_ir_density"]),
        jammer_density=float(scenario["adversary_jammer_density"]),
        altitude_m=int(route_optimization_profile.get("recommended_altitude_m", altitude_m)),
        speed_kmh=float(autopilot_profile.get("target_speed_kmh", flight_speed_kmh)),
        overall_detectability=float(terrain_masking_profile.get("adjusted_overall_score", overall_score)),
        visual_score=float(terrain_masking_profile.get("adjusted_visual_score", visual_score)),
        thermal_score=thermal_score,
        sensor_detection_range_km=float(sensor_model_profile.get("max_likely_detection_km", 0.0)),
        terrain_masking_score=float(terrain_masking_profile.get("masking_score", 0.0)),
        route_score=float(route_optimization_profile.get("optimized_score", 0.0)),
        threat_zone_km=threat_zone_km,
        power_system=profile["power_system"],
        radar_frequency_ghz=float(scenario["radar_frequency_ghz"]),
        radar_tx_power_kw=float(scenario["radar_tx_power_kw"]),
        effective_size_m=effective_size_m,
    )
    mission_profile = simulate_mission_phases(
        profile=profile,
        payload_weight_g=payload_weight_g,
        cruise_speed_kmh=flight_speed_kmh,
        wind_speed_kmh=wind_speed_kmh,
        temperature_c=temperature_c,
        cruise_altitude_m=altitude_m,
        elevation_gain_m=elevation_gain_m,
        gustiness=gustiness,
        terrain_penalty=terrain_penalty,
        stealth_drag_penalty=stealth_drag_penalty,
        battery_capacity_wh=(result.get("battery_derated_Wh") if profile["power_system"] == "Battery" else None),
        fuel_tank_l=(result.get("usable_fuel_L") if profile["power_system"] == "ICE" else None),
        loiter_minutes=float(coupled_loiter_profile.get("allowed_loiter_min", loiter_minutes)) if "coupled_loiter_profile" in locals() else loiter_minutes,
        include_rtb=include_rtb,
    )
    nav_profile_v2 = compute_gnss_denied_navigation_v2(
        enabled=True,
        fusion_quality=float(scenario.get("fusion_quality", 1.0)),
        drift_sensitivity=float(scenario.get("drift_sensitivity", 1.0)),
        map_uncertainty_factor=float(scenario.get("map_uncertainty_factor", 0.25)),
        update_gain=float(scenario.get("gnss_update_gain", 0.55)),
        flight_time_minutes=flight_time_minutes,
        total_distance_km=(result.get("V_effective_ms", max(1.0, flight_speed_kmh / 3.6)) * 3.6 * flight_time_minutes) / 60.0,
        speed_kmh=float(autopilot_profile.get("target_speed_kmh", flight_speed_kmh)),
        terrain_masking_score=float(terrain_masking_profile.get("masking_score", 0.0)),
        jammer_risk=float(adversary_profile.get("jammer_risk", 0.0)),
        route_score=float(route_optimization_profile.get("optimized_score", 0.0)),
        waypoints=waypoints,
    )

    mission_score = max(0.0, min(100.0,
        0.30 * min(100.0, flight_time_minutes) +
        0.20 * (100.0 - float(terrain_masking_profile.get("adjusted_overall_score", overall_score))) +
        0.15 * float(sensor_model_profile.get("baseline_probability", 0.0)) / 2.0 +
        0.15 * float(mission_profile.get("mission_feasible", True)) * 100.0 +
        0.10 * float(nav_profile_v2.get("navigation_confidence", 100.0)) +
        0.10 * float(adversary_profile.get("survivability_score", 100.0))
    ))

    return {
        "label": scenario["label"],
        "speed_kmh": round(flight_speed_kmh, 1),
        "altitude_m": int(altitude_m),
        "loiter_minutes": round(loiter_minutes, 1),
        "endurance_min": round(flight_time_minutes, 1),
        "detectability_score": round(float(terrain_masking_profile.get("adjusted_overall_score", overall_score)), 1),
        "mission_score": round(mission_score, 1),
        "survivability_score": round(float(adversary_profile.get("survivability_score", 100.0)), 1),
        "nav_confidence": round(float(nav_profile_v2.get("navigation_confidence", 100.0)), 1),
        "mission_feasible": bool(mission_profile.get("mission_feasible", True)),
        "radar_detect_prob": round(float(adversary_profile.get("radar_detection_probability_pct", 0.0)), 1),
        "allowed_loiter_min": round(float(coupled_loiter_profile.get("allowed_loiter_min", loiter_minutes)) if "coupled_loiter_profile" in locals() else float(loiter_minutes), 1),
    }


def render_scenario_comparison_panel(
    enabled: bool,
    profile: Dict[str, Any],
    base_inputs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    st.markdown(
        "<div class='section-card'><div class='section-title'>Scenario Comparison Engine</div>"
        "<div class='section-note'>Scientifically stronger comparison using full-stack mission reruns across three mission configurations.</div></div>",
        unsafe_allow_html=True,
    )
    if not enabled:
        st.info("Scenario Comparison Engine is disabled.")
        return []

    scenarios = build_scenario_variants(base_inputs)
    results = [evaluate_full_stack_scenario(profile, s) for s in scenarios]

    cols = st.columns(3)
    for col, res in zip(cols, results):
        with col:
            st.markdown(f"**{res['label']}**")
            st.metric("Mission Score", f"{res['mission_score']:.1f}/100")
            st.metric("Endurance", f"{res['endurance_min']:.1f} min")
            st.metric("Detectability", f"{res['detectability_score']:.1f}/100")
            st.metric("Nav Confidence", f"{res['nav_confidence']:.1f}/100")
            st.caption(f"Speed {res['speed_kmh']:.1f} km/h | Alt {res['altitude_m']} m | Loiter {res['loiter_minutes']:.1f} min (allowed {res.get('allowed_loiter_min', res['loiter_minutes']):.1f}) | Survivability {res['survivability_score']:.1f}/100 | Radar {res.get('radar_detect_prob', 0.0):.1f}%")

    df_cmp = pd.DataFrame(results)
    st.dataframe(df_cmp, use_container_width=True)

    best = max(results, key=lambda x: x["mission_score"]) if results else None
    if best:
        st.success(f"Recommended comparison winner: {best['label']} (Mission Score {best['mission_score']:.1f}/100)")
    return results


def compute_gnss_denied_navigation_v2(
    enabled: bool,
    fusion_quality: float,
    drift_sensitivity: float,
    map_uncertainty_factor: float,
    update_gain: float,
    flight_time_minutes: float,
    total_distance_km: float,
    speed_kmh: float,
    terrain_masking_score: float,
    jammer_risk: float,
    route_score: float,
    waypoints: List[Tuple[float, float]],
) -> Dict[str, Any]:
    # Planning-grade GNSS-denied navigation v2 with EKF-style state/covariance surrogate
    import math
    result = {
        "enabled": enabled,
        "active": False,
        "fusion_health_score": 100.0,
        "estimated_drift_km": 0.0,
        "map_uncertainty_km": 0.0,
        "navigation_confidence": 100.0,
        "recommended_mode": "Nominal",
        "cov_trace": 0.0,
        "state_vector": [0.0] * 8,
        "estimated_path": [],
        "actions": [],
    }
    if not enabled:
        return result

    jammer_factor = max(0.0, min(1.0, jammer_risk / 100.0))
    route_factor = max(0.0, min(1.0, route_score / 100.0))
    masking_bonus = max(0.0, min(1.0, terrain_masking_score / 100.0))
    fusion_quality_n = max(0.4, min(1.6, float(fusion_quality)))
    drift_sens = max(0.4, min(1.8, float(drift_sensitivity)))
    gain_base = max(0.15, min(0.90, float(update_gain)))

    pts = [(0.0, 0.0)] + list(waypoints)
    if len(pts) < 2:
        pts = [(0.0, 0.0), (max(0.1, total_distance_km), 0.0)]

    # state vector [x, y, vx, vy, psi, bg, bax, bay]
    x = [0.0, 0.0, max(0.1, speed_kmh / 3600.0), 0.0, 0.0, 0.0, 0.0, 0.0]
    P = [1e-4, 1e-4, 5e-5, 5e-5, 1e-3, 5e-4, 5e-4, 5e-4]

    q_pos = 2e-4 * drift_sens * (1.0 + 1.6 * jammer_factor + 0.5 * route_factor)
    q_vel = 1e-4 * drift_sens * (1.0 + 1.4 * jammer_factor)
    q_heading = 6e-4 * drift_sens * (1.0 + 1.2 * jammer_factor)
    q_bias = 2e-4 * drift_sens * (1.0 + 1.8 * jammer_factor)

    nominal_dense = []
    for i in range(1, len(pts)):
        p0, p1 = pts[i-1], pts[i]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        d = max(1e-6, (dx*dx + dy*dy) ** 0.5)
        sub = max(2, int(d * 4))
        for k in range(sub):
            frac = k / sub
            nominal_dense.append((p0[0] + frac * dx, p0[1] + frac * dy))
    nominal_dense.append(pts[-1])

    dt_s = max(4.0, (flight_time_minutes * 60.0) / max(8, len(nominal_dense)))
    update_interval = max(2, int(6 - min(3.0, 2.5 * fusion_quality_n) + 3.0 * jammer_factor))

    est_path = []
    for i, (nx, ny) in enumerate(nominal_dense):
        desired_heading = math.atan2(ny - x[1], nx - x[0]) if (abs(nx - x[0]) + abs(ny - x[1])) > 1e-6 else x[4]
        heading_err = desired_heading - x[4]
        while heading_err > math.pi:
            heading_err -= 2 * math.pi
        while heading_err < -math.pi:
            heading_err += 2 * math.pi

        x[4] += 0.15 * heading_err * (fusion_quality_n / 1.5) * (1.0 - 0.5 * jammer_factor)
        x[5] += q_bias * 0.05
        x[6] += q_bias * 0.03
        x[7] -= q_bias * 0.02

        speed_kmps = max(0.00005, speed_kmh / 3600.0)
        x[2] = speed_kmps * math.cos(x[4]) + x[6] * 0.01
        x[3] = speed_kmps * math.sin(x[4]) + x[7] * 0.01
        x[0] += x[2] * dt_s
        x[1] += x[3] * dt_s

        P[0] += q_pos
        P[1] += q_pos
        P[2] += q_vel
        P[3] += q_vel
        P[4] += q_heading
        P[5] += q_bias
        P[6] += q_bias
        P[7] += q_bias

        if i % update_interval == 0:
            gain = max(0.12, min(0.90, gain_base * (fusion_quality_n / 1.5) * (1.0 - 0.55 * jammer_factor)))
            x[0] = (1 - gain) * x[0] + gain * nx
            x[1] = (1 - gain) * x[1] + gain * ny
            P[0] *= max(0.35, 1.0 - 0.55 * gain)
            P[1] *= max(0.35, 1.0 - 0.55 * gain)
            P[4] *= max(0.45, 1.0 - 0.45 * gain)

        est_path.append((round(x[0], 4), round(x[1], 4)))

    final_nom = nominal_dense[-1]
    drift_km = math.sqrt((x[0] - final_nom[0])**2 + (x[1] - final_nom[1])**2)
    map_uncertainty_km = max(0.0, (0.02 * total_distance_km + 0.45 * map_uncertainty_factor) * (1.0 + 0.9 * jammer_factor))
    fusion_health = 100.0 * max(0.0, min(1.0, 0.78 * (fusion_quality_n / 1.5) + 0.10 * masking_bonus + 0.12 * (1.0 - jammer_factor)))
    cov_trace = P[0] + P[1] + P[4]
    nav_conf = max(0.0, min(fusion_health, 100.0 - (55.0 * drift_km + 28.0 * map_uncertainty_km + 18.0 * cov_trace)))

    mode = "Nominal"
    if nav_conf < 40:
        mode = "Degraded"
    elif nav_conf < 65:
        mode = "Caution"

    actions = []
    if fusion_health < 60:
        actions.append("Sensor-fusion health is degraded — shorten exposed legs and reduce dependence on precise waypoint timing.")
    else:
        actions.append("Sensor-fusion health is acceptable for planning-grade degraded navigation.")
    if drift_km >= 1.0:
        actions.append("Estimated path drift is high — tighten waypoint spacing or shorten GNSS-denied segments.")
    elif drift_km >= 0.4:
        actions.append("Estimated path drift is moderate — maintain conservative routing and stronger aiding cadence.")
    if map_uncertainty_km >= 0.8:
        actions.append("Map uncertainty is significant — confirm terrain and landmark assumptions before relying on masked routing.")
    elif map_uncertainty_km >= 0.3:
        actions.append("Map uncertainty is present — preserve broader reserve margins for degraded navigation.")
    if jammer_factor >= 0.6:
        actions.append("Jammer pressure is high — expect faster covariance growth and more frequent aiding dropouts.")
    if nav_conf < 40:
        actions.append("Navigation confidence is low — recommend abort or route simplification under GNSS-denied conditions.")
    elif nav_conf < 65:
        actions.append("Navigation confidence is moderate — favor shorter legs and stronger fusion posture.")
    else:
        actions.append("Navigation confidence is strong enough for planning-grade GNSS-denied assessment.")

    result.update({
        "active": True,
        "fusion_health_score": round(fusion_health, 1),
        "estimated_drift_km": round(drift_km, 3),
        "map_uncertainty_km": round(map_uncertainty_km, 3),
        "navigation_confidence": round(nav_conf, 1),
        "recommended_mode": mode,
        "cov_trace": round(cov_trace, 4),
        "state_vector": [round(v, 5) for v in x],
        "estimated_path": est_path,
        "actions": actions[:5],
    })
    return result


def render_gnss_denied_navigation_v2_panel(nav_profile: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>GNSS-Denied Navigation v2</div>"
        "<div class='section-note'>Planning-grade degraded-navigation estimate with state vector, covariance growth, measurement updates, and estimated-path drift.</div></div>",
        unsafe_allow_html=True,
    )
    if not nav_profile.get("enabled", False):
        st.info("GNSS-Denied Navigation v2 is disabled.")
        return

    mode = nav_profile.get("recommended_mode", "Nominal")
    if mode == "Degraded":
        st.error(f"Navigation mode: {mode}")
    elif mode == "Caution":
        st.warning(f"Navigation mode: {mode}")
    else:
        st.success(f"Navigation mode: {mode}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Fusion Health", f"{nav_profile.get('fusion_health_score', 100.0):.1f}/100")
    with c2:
        st.metric("Estimated Drift", f"{nav_profile.get('estimated_drift_km', 0.0):.3f} km")
    with c3:
        st.metric("Map Uncertainty", f"{nav_profile.get('map_uncertainty_km', 0.0):.3f} km")

    c4, c5 = st.columns(2)
    with c4:
        st.metric("Navigation Confidence", f"{nav_profile.get('navigation_confidence', 100.0):.1f}/100")
    with c5:
        st.metric("Covariance Trace", f"{nav_profile.get('cov_trace', 0.0):.4f}")

    st.caption(f"State vector [x, y, vx, vy, psi, bg, bax, bay]: {nav_profile.get('state_vector', [])}")

    for action in nav_profile.get("actions", []):
        if "abort" in action.lower() or "degraded" in action.lower() or "high" in action.lower():
            st.warning(action)
        else:
            st.info(action)


def compute_coupled_loiter_feasibility(
    requested_loiter_min: float,
    radar_detect_probability_pct: float,
    combined_threat_score: float,
    route_mode: str,
) -> Dict[str, Any]:
    loiter_penalty = 0.0
    if radar_detect_probability_pct >= 70:
        loiter_penalty += 0.45
    elif radar_detect_probability_pct >= 45:
        loiter_penalty += 0.25
    if combined_threat_score >= 75:
        loiter_penalty += 0.35
    elif combined_threat_score >= 50:
        loiter_penalty += 0.20
    if route_mode == "Stealth-Biased":
        loiter_penalty *= 0.85

    allowed_loiter = max(0.0, float(requested_loiter_min) * max(0.25, 1.0 - loiter_penalty))
    posture = "Nominal"
    if allowed_loiter + 1e-6 < requested_loiter_min * 0.5:
        posture = "Restricted"
    elif allowed_loiter + 1e-6 < requested_loiter_min:
        posture = "Reduced"
    return {
        "requested_loiter_min": round(float(requested_loiter_min), 2),
        "allowed_loiter_min": round(float(allowed_loiter), 2),
        "loiter_penalty": round(float(loiter_penalty), 3),
        "posture": posture,
    }


def render_coupled_threat_panel(coupled_profile: Dict[str, Any]):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Threat-Coupled Mission Effects</div>"
        "<div class='section-note'>Adversary radar and jammer effects now feed route cost, navigation degradation, and loiter feasibility.</div></div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Requested Loiter", f"{coupled_profile.get('requested_loiter_min', 0.0):.1f} min")
    with c2:
        st.metric("Allowed Loiter", f"{coupled_profile.get('allowed_loiter_min', 0.0):.1f} min")
    with c3:
        st.metric("Loiter Posture", coupled_profile.get('posture', 'Nominal'))

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

def render_mission_hero(endurance_min: float, total_distance_km: float, best_range_km: float, detectability_label: str, detectability_color: str, power_system: str):
    return f"""
    <div class='mission-hero'>
        <div class='mission-kicker'>Mission Summary</div>
        <div class='mission-hero-grid'>
            <div>
                <div class='mission-label'>Endurance</div>
                <div class='mission-value'>{endurance_min:.1f} min</div>
            </div>
            <div>
                <div class='mission-label'>Total Distance</div>
                <div class='mission-value'>{total_distance_km:.1f} km</div>
            </div>
            <div>
                <div class='mission-label'>Best Heading Range</div>
                <div class='mission-value'>{best_range_km:.1f} km</div>
            </div>
            <div>
                <div class='mission-label'>Detectability</div>
                <div class='mission-value' style='color:{detectability_color};'>{detectability_label}</div>
            </div>
            <div>
                <div class='mission-label'>Power System</div>
                <div class='mission-value'>{power_system}</div>
            </div>
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


def detectability_ai_suggestions(
    visual_score: float,
    thermal_score: float,
    overall_score: float,
    confidence: float,
    altitude_m: float,
    speed_kmh: float,
    cloud_cover: float,
    gustiness: float,
    stealth_factor: float,
    power_system: str,
    delta_T: float,
) -> List[Tuple[str, str]]:
    suggestions: List[Tuple[str, str]] = []

    if thermal_score > 65:
        suggestions.append(("error", "🔥 High IR signature: Reduce sustained high-power output or shorten time at maximum climb / thrust."))
        if delta_T > 25:
            suggestions.append(("warning", "🌡️ Elevated ΔT: Increase convective cooling with a more efficient cruise segment or reduce engine load."))
        if power_system == 'ICE':
            suggestions.append(("warning", "⛽ ICE platform: Reserve Hybrid Assist or reduced-power ingress for the highest-threat segments."))
    elif thermal_score < 35:
        suggestions.append(("success", "❄️ Low IR signature: Current thermal profile is favorable for reduced thermal exposure."))

    if visual_score > 65:
        suggestions.append(("error", "👁️ High visual detectability: Increase altitude, use terrain masking, or reduce straight-line exposure."))
        if speed_kmh > 120:
            suggestions.append(("info", "💨 Current speed increases visual observability. Consider reducing speed while inside the threat envelope."))
        if cloud_cover < 30:
            suggestions.append(("warning", "☁️ Low cloud cover limits concealment. Avoid prolonged exposure in open sky backgrounds."))
    elif visual_score < 35:
        suggestions.append(("success", "🌫️ Low visual detectability: Current geometry and environment support a relatively covert profile."))

    if cloud_cover > 70:
        suggestions.append(("success", "☁️ High cloud cover is favorable for both visual and IR concealment in this heuristic model."))

    if gustiness > 5:
        suggestions.append(("info", "🌪️ High gustiness may reduce detection consistency, but it also increases control and energy penalties."))

    if stealth_factor > 1.2:
        suggestions.append(("warning", "🥷 High stealth drag factor is helping signature management but materially reducing endurance margins."))

    if altitude_m < 300 and overall_score > 50:
        suggestions.append(("warning", "📉 Low-altitude exposure is increasing detectability. Climb if the mission and threat picture allow it."))
    elif altitude_m > 800 and visual_score > thermal_score:
        suggestions.append(("info", "📈 Altitude is helping thermal concealment more than visual concealment. Route choice and cloud timing matter here."))

    if confidence < 60:
        suggestions.append(("warning", "⚠️ Low detectability confidence: treat these scores cautiously because environmental uncertainty is elevated."))
    elif confidence > 85:
        suggestions.append(("success", "📡 High confidence: the detectability estimate is relatively stable under the current environmental assumptions."))

    if overall_score > 70:
        suggestions.append(("error", "🚨 Overall detectability is high. Adjust altitude, timing, speed, or exposure duration before committing to ingress."))
    elif overall_score < 40:
        suggestions.append(("success", "✅ Overall detectability is low. Current settings are favorable for lower exposure risk."))

    return suggestions[:5]

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


@dataclass
class MissionPhase:
    name: str
    duration_min: float
    power_W: float = 0.0
    energy_Wh: float = 0.0
    fuel_L: float = 0.0
    notes: str = ""


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



def simulate_mission_phases(
    profile: Dict[str, Any],
    payload_weight_g: int,
    cruise_speed_kmh: float,
    wind_speed_kmh: float,
    temperature_c: float,
    cruise_altitude_m: int,
    elevation_gain_m: int,
    gustiness: int,
    terrain_penalty: float,
    stealth_drag_penalty: float,
    battery_capacity_wh: Optional[float] = None,
    fuel_tank_l: Optional[float] = None,
    loiter_minutes: float = 0.0,
    include_rtb: bool = False,
) -> Dict[str, Any]:
    """
    Fleet-wide educational mission timeline:
    climb -> cruise -> optional loiter -> descent -> optional RTB

    Reserve phases are budgeted first so cruise does not consume the
    entire mission energy/fuel budget.
    """

    phases: List[MissionPhase] = []
    warnings: List[str] = []

    total_mass_kg = profile["base_weight_kg"] + (payload_weight_g / 1000.0)
    weight_N = total_mass_kg * G0

    if profile["type"] == "rotor":
        climb_rate_mps = 2.0
        descent_rate_mps = 2.0
        climb_mode = "Hover"
        cruise_mode = "Forward Flight"
        descent_mode = "Forward Flight"
    else:
        climb_rate_mps = 3.0
        descent_rate_mps = 2.5
        climb_mode = "Forward Flight"
        cruise_mode = "Forward Flight"
        descent_mode = "Loiter"

    climb_altitude_m = max(0.0, float(cruise_altitude_m + max(0.0, elevation_gain_m)))
    descent_altitude_m = climb_altitude_m
    climb_time_min = 0.0 if climb_altitude_m <= 0 else climb_altitude_m / max(0.1, climb_rate_mps) / 60.0
    descent_time_min = 0.0 if descent_altitude_m <= 0 else descent_altitude_m / max(0.1, descent_rate_mps) / 60.0

    def get_phase_result(flight_mode: str, speed_kmh: float, altitude_m: int, energy_wh: Optional[float], fuel_l: Optional[float]):
        if profile["power_system"] == "Battery":
            batt_wh = float(energy_wh if energy_wh is not None else battery_capacity_wh or profile.get("battery_wh", 0.0))
            return simulate_battery_aircraft(
                profile=profile,
                payload_weight_g=payload_weight_g,
                flight_speed_kmh=speed_kmh,
                wind_speed_kmh=wind_speed_kmh,
                temperature_c=temperature_c,
                altitude_m=altitude_m,
                elevation_gain_m=0,
                flight_mode=flight_mode,
                gustiness=gustiness,
                terrain_penalty=terrain_penalty,
                stealth_drag_penalty=stealth_drag_penalty,
                battery_capacity_wh=batt_wh,
            )
        tank_l = float(fuel_l if fuel_l is not None else fuel_tank_l or profile.get("fuel_tank_l", 0.0))
        return simulate_ice_aircraft(
            profile=profile,
            payload_weight_g=payload_weight_g,
            flight_speed_kmh=speed_kmh,
            wind_speed_kmh=wind_speed_kmh,
            temperature_c=temperature_c,
            altitude_m=altitude_m,
            elevation_gain_m=0,
            flight_mode=flight_mode,
            gustiness=gustiness,
            terrain_penalty=terrain_penalty,
            stealth_drag_penalty=stealth_drag_penalty,
            fuel_tank_l=tank_l,
        )

    # Starting available resources
    if profile["power_system"] == "Battery":
        total_available = float(battery_capacity_wh if battery_capacity_wh is not None else profile.get("battery_wh", 0.0))
    else:
        total_available = float(fuel_tank_l if fuel_tank_l is not None else profile.get("fuel_tank_l", 0.0))

    # -------------------------
    # CLIMB (committed first)
    # -------------------------
    climb_speed_kmh = max(20.0, 0.85 * cruise_speed_kmh)
    climb_res = get_phase_result(climb_mode, climb_speed_kmh, int(max(0, cruise_altitude_m)), total_available if profile["power_system"] == "Battery" else None, total_available if profile["power_system"] == "ICE" else None)

    if profile["power_system"] == "Battery":
        climb_power_W = float(climb_res["total_draw_W"])
        climb_extra_W = weight_N * climb_rate_mps
        climb_total_W = climb_power_W + climb_extra_W
        climb_energy_Wh = climb_total_W * climb_time_min / 60.0
        climb_energy_Wh = min(climb_energy_Wh, max(0.0, total_available))
        total_available = max(0.0, total_available - climb_energy_Wh)
        phases.append(MissionPhase("Climb", climb_time_min, climb_total_W, climb_energy_Wh, 0.0, "Steady-state power plus climb work"))
    else:
        climb_power_W = float(climb_res["total_power_W"])
        climb_extra_W = weight_N * climb_rate_mps
        climb_total_W = climb_power_W + climb_extra_W
        climb_fuel_lph = bsfc_fuel_burn_lph(climb_total_W, profile["bsfc_gpkwh"], profile["fuel_density_kgpl"])
        climb_fuel_L = climb_fuel_lph * climb_time_min / 60.0
        climb_fuel_L = min(climb_fuel_L, max(0.0, total_available))
        total_available = max(0.0, total_available - climb_fuel_L)
        phases.append(MissionPhase("Climb", climb_time_min, climb_total_W, 0.0, climb_fuel_L, "Steady-state power plus climb work"))

    # -------------------------
    # Reserve phases BEFORE cruise
    # -------------------------
    descent_speed_kmh = max(20.0, 0.75 * cruise_speed_kmh)
    descent_res = get_phase_result(descent_mode, descent_speed_kmh, int(max(0, cruise_altitude_m // 2)), total_available if profile["power_system"] == "Battery" else None, total_available if profile["power_system"] == "ICE" else None)

    loiter_minutes_requested = max(0.0, float(loiter_minutes))
    rtb_minutes_est = 20.0 if include_rtb else 0.0

    if profile["power_system"] == "Battery":
        descent_power_W = 0.60 * float(descent_res["total_draw_W"])
        descent_reserve = descent_power_W * descent_time_min / 60.0

        loiter_power_W = 0.0
        loiter_reserve = 0.0
        if loiter_minutes_requested > 0:
            loiter_res = get_phase_result("Loiter", max(20.0, 0.70 * cruise_speed_kmh), int(max(0, cruise_altitude_m)), total_available, None)
            loiter_power_W = float(loiter_res["total_draw_W"])
            loiter_reserve = loiter_power_W * loiter_minutes_requested / 60.0

        rtb_power_W = 0.0
        rtb_reserve = 0.0
        if include_rtb:
            rtb_res = get_phase_result("Forward Flight", cruise_speed_kmh, int(max(0, cruise_altitude_m // 2)), total_available, None)
            rtb_power_W = float(rtb_res["total_draw_W"])
            rtb_reserve = rtb_power_W * rtb_minutes_est / 60.0

        mandatory_reserve = descent_reserve + rtb_reserve
        if mandatory_reserve > total_available:
            warnings.append("Insufficient energy for full descent + RTB reserve. Mission is not fully recoverable.")
            if mandatory_reserve > 0:
                scale = total_available / mandatory_reserve
                descent_reserve *= scale
                rtb_reserve *= scale
                rtb_minutes_est *= scale

        remaining_after_mandatory = max(0.0, total_available - (descent_reserve + rtb_reserve))

        loiter_minutes_eff = loiter_minutes_requested
        if loiter_reserve > remaining_after_mandatory:
            if loiter_minutes_requested > 0:
                loiter_minutes_eff = (remaining_after_mandatory / max(1.0, loiter_power_W)) * 60.0
                warnings.append("Requested loiter time is not fully achievable. Loiter was reduced to fit reserve constraints.")
                loiter_reserve = loiter_power_W * loiter_minutes_eff / 60.0
            else:
                loiter_reserve = 0.0

        cruise_budget = max(0.0, total_available - descent_reserve - rtb_reserve - loiter_reserve)
        cruise_res = get_phase_result(cruise_mode, cruise_speed_kmh, int(max(0, cruise_altitude_m)), cruise_budget, None)
        cruise_power_W = float(cruise_res["total_draw_W"])
        cruise_time_min = (cruise_budget / max(1.0, cruise_power_W)) * 60.0 if cruise_power_W > 0 else 0.0

        phases.append(MissionPhase("Cruise", cruise_time_min, cruise_power_W, cruise_budget, 0.0, "Cruise budgeted after descent / loiter / RTB reserve"))

        if loiter_minutes_eff > 0:
            phases.append(MissionPhase("Loiter", loiter_minutes_eff, loiter_power_W, loiter_reserve, 0.0, "Optional loiter phase"))

        phases.append(MissionPhase("Descent", descent_time_min, descent_power_W, descent_reserve, 0.0, "Reduced thrust descent approximation"))

        if include_rtb:
            phases.append(MissionPhase("RTB", rtb_minutes_est, rtb_power_W, rtb_reserve, 0.0, "Return-to-base reserve estimate"))

        remaining_energy_Wh = max(0.0, total_available - (cruise_budget + loiter_reserve + descent_reserve + rtb_reserve))

        return {
            "phases": phases,
            "total_time_min": sum(p.duration_min for p in phases),
            "total_energy_Wh": sum(p.energy_Wh for p in phases),
            "total_fuel_L": 0.0,
            "remaining_energy_Wh": remaining_energy_Wh,
            "remaining_fuel_L": None,
            "warnings": warnings,
            "mission_feasible": len([w for w in warnings if "not fully recoverable" in w]) == 0,
        }

    # ICE branch
    descent_power_W = 0.60 * float(descent_res["total_power_W"])
    descent_fuel_lph = bsfc_fuel_burn_lph(descent_power_W, profile["bsfc_gpkwh"], profile["fuel_density_kgpl"])
    descent_reserve = descent_fuel_lph * descent_time_min / 60.0

    loiter_power_W = 0.0
    loiter_reserve = 0.0
    if loiter_minutes_requested > 0:
        loiter_res = get_phase_result("Loiter", max(20.0, 0.70 * cruise_speed_kmh), int(max(0, cruise_altitude_m)), None, total_available)
        loiter_power_W = float(loiter_res["total_power_W"])
        loiter_fuel_lph = float(loiter_res["fuel_burn_L_per_hr"])
        loiter_reserve = loiter_fuel_lph * loiter_minutes_requested / 60.0

    rtb_power_W = 0.0
    rtb_reserve = 0.0
    if include_rtb:
        rtb_res = get_phase_result("Forward Flight", cruise_speed_kmh, int(max(0, cruise_altitude_m // 2)), None, total_available)
        rtb_power_W = float(rtb_res["total_power_W"])
        rtb_fuel_lph = float(rtb_res["fuel_burn_L_per_hr"])
        rtb_reserve = rtb_fuel_lph * rtb_minutes_est / 60.0

    mandatory_reserve = descent_reserve + rtb_reserve
    if mandatory_reserve > total_available:
        warnings.append("Insufficient fuel for full descent + RTB reserve. Mission is not fully recoverable.")
        if mandatory_reserve > 0:
            scale = total_available / mandatory_reserve
            descent_reserve *= scale
            rtb_reserve *= scale
            rtb_minutes_est *= scale

    remaining_after_mandatory = max(0.0, total_available - (descent_reserve + rtb_reserve))

    loiter_minutes_eff = loiter_minutes_requested
    if loiter_reserve > remaining_after_mandatory:
        if loiter_minutes_requested > 0:
            loiter_minutes_eff = (remaining_after_mandatory / max(1e-6, loiter_fuel_lph)) * 60.0 if loiter_power_W > 0 else 0.0
            warnings.append("Requested loiter time is not fully achievable. Loiter was reduced to fit reserve constraints.")
            loiter_reserve = loiter_fuel_lph * loiter_minutes_eff / 60.0
        else:
            loiter_reserve = 0.0

    cruise_budget = max(0.0, total_available - descent_reserve - rtb_reserve - loiter_reserve)
    cruise_res = get_phase_result(cruise_mode, cruise_speed_kmh, int(max(0, cruise_altitude_m)), None, cruise_budget)
    cruise_power_W = float(cruise_res["total_power_W"])
    cruise_fuel_lph = float(cruise_res["fuel_burn_L_per_hr"])
    cruise_time_min = (cruise_budget / max(1e-6, cruise_fuel_lph)) * 60.0 if cruise_fuel_lph > 0 else 0.0

    phases.append(MissionPhase("Cruise", cruise_time_min, cruise_power_W, 0.0, cruise_budget, "Cruise budgeted after descent / loiter / RTB reserve"))

    if loiter_minutes_eff > 0:
        phases.append(MissionPhase("Loiter", loiter_minutes_eff, loiter_power_W, 0.0, loiter_reserve, "Optional loiter phase"))

    phases.append(MissionPhase("Descent", descent_time_min, descent_power_W, 0.0, descent_reserve, "Reduced thrust descent approximation"))

    if include_rtb:
        phases.append(MissionPhase("RTB", rtb_minutes_est, rtb_power_W, 0.0, rtb_reserve, "Return-to-base reserve estimate"))

    remaining_fuel_L = max(0.0, total_available - (cruise_budget + loiter_reserve + descent_reserve + rtb_reserve))

    return {
        "phases": phases,
        "total_time_min": sum(p.duration_min for p in phases),
        "total_energy_Wh": 0.0,
        "total_fuel_L": sum(p.fuel_L for p in phases),
        "remaining_energy_Wh": None,
        "remaining_fuel_L": remaining_fuel_L,
        "warnings": warnings,
        "mission_feasible": len([w for w in warnings if "not fully recoverable" in w]) == 0,
    }


def render_mission_phase_panel(mission_profile: Dict[str, Any], power_system: str):
    st.markdown(
        "<div class='section-card'><div class='section-title'>Mission Phase Simulation</div>"
        "<div class='section-note'>Climb, cruise, loiter, descent, and optional return-to-base timeline.</div></div>",
        unsafe_allow_html=True,
    )

    if mission_profile.get('mission_feasible', True):
        st.success('Mission reserve check: PASS')
    else:
        st.error('Mission reserve check: FAIL')

    for warning in mission_profile.get('warnings', []):
        st.warning(warning)

    rows = []
    for p in mission_profile["phases"]:
        row = {
            "Phase": p.name,
            "Time (min)": round(p.duration_min, 2),
            "Power (W)": round(p.power_W, 1),
            "Notes": p.notes,
        }
        if power_system == "Battery":
            row["Energy (Wh)"] = round(p.energy_Wh, 2)
        else:
            row["Fuel (L)"] = round(p.fuel_L, 3)
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Mission Time", f"{mission_profile['total_time_min']:.1f} min")
    with c2:
        if power_system == "Battery":
            st.metric("Total Mission Energy", f"{mission_profile['total_energy_Wh']:.1f} Wh")
        else:
            st.metric("Total Mission Fuel", f"{mission_profile['total_fuel_L']:.2f} L")
    with c3:
        st.metric("Phase Count", f"{len(mission_profile['phases'])}")

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


st.sidebar.header('Operator Control Panel')
st.sidebar.caption('Grouped mission controls for platform setup, autonomy, sensing, threats, navigation, performance, and outputs.')

with st.sidebar.expander('Platform & Mission Mode', expanded=True):
    drone_model = st.selectbox('Drone Model', list(UAV_PROFILES.keys()))
    system_mode = st.radio(
        'System Mode',
        ['Engineering Mode', 'Swarm / Mission Ops Mode'],
        index=0,
    )
    compact_layout = st.toggle('Compact Layout', value=False)

with st.sidebar.expander('Operator Display & Output Panels', expanded=False):
    show_advanced = st.toggle('Show Advanced Metrics', value=True)
    show_validation = st.toggle('Show Validation Panel', value=True)
    show_detectability = st.toggle('Show Detectability Panel', value=True)
    show_live_simulation = st.toggle('Enable Live Simulation', value=True)
    show_json_preview = st.toggle('Show JSON Export Preview', value=True)
    mission_visualization = st.toggle('Enable 2D/3D Mission Visualization', value=True)
    scenario_comparison_engine = st.toggle('Enable Scenario Comparison Engine', value=True)

with st.sidebar.expander('Autonomy & Tactical Logic', expanded=False):
    detectability_autopilot = st.toggle('Enable Detectability Autopilot', value=True)
    route_optimization = st.toggle('Enable Route Optimization', value=True)
    llm_tactical_mode = st.toggle('Enable LLM Tactical Mode', value=True)
    swarm_intelligence_upgrade = st.toggle('Enable Swarm Intelligence Upgrade', value=True)

with st.sidebar.expander('Sensing, Detectability & Threats', expanded=False):
    sensor_modeling = st.toggle('Enable Sensor Modeling', value=True)
    terrain_masking = st.toggle('Enable Terrain Masking', value=True)
    terrain_masking_v2 = st.toggle('Enable Terrain Masking v2', value=True)
    adversary_simulation = st.toggle('Enable Adversary Simulation', value=True)

with st.sidebar.expander('Navigation & Contested Environment', expanded=False):
    gnss_denied_navigation = st.toggle('Enable Legacy GNSS Nav (compatibility)', value=False)
    gnss_denied_navigation_v2 = st.toggle('Enable GNSS-Denied Navigation v2', value=True)

with st.sidebar.expander('Performance & Envelope', expanded=False):
    flight_envelope_enforcement = st.toggle('Enable Flight Envelope Enforcement', value=True)
    degradation_modeling = st.toggle('Enable Battery + Fuel Degradation Modeling', value=True)

with st.sidebar.expander('Debug & Validation Controls', expanded=False):
    debug_mode = st.toggle('Enable Debug Mode', value=False)
    allow_pack_override = st.toggle('Allow Battery Override (debug)', value=False) if debug_mode else False

st.sidebar.markdown('---')
st.sidebar.caption(
    'Active upgrades: '
    f"{sum(bool(x) for x in [detectability_autopilot, route_optimization, swarm_intelligence_upgrade, terrain_masking, sensor_modeling, mission_visualization, llm_tactical_mode, adversary_simulation, gnss_denied_navigation, flight_envelope_enforcement, degradation_modeling, terrain_masking_v2, scenario_comparison_engine, gnss_denied_navigation_v2])}/14"
)
profile = UAV_PROFILES[drone_model]
st.info(f"**AI Capabilities:** {profile.get('ai_capabilities', '—')}")
st.caption(f"Base weight: {profile['base_weight_kg']} kg — Max payload: {profile['max_payload_g']} g")
st.caption(f"Power system: `{profile['power_system']}` | Type: `{profile['type']}`")

st.markdown(
    f"""
<div class="section-card">
  <div class="section-title">Operator Console Status</div>
  <div class="section-note">
    Mode: <b>{system_mode}</b> |
    Visualization: <b>{'ON' if mission_visualization else 'OFF'}</b> |
    Tactical Briefing: <b>{'ON' if llm_tactical_mode else 'OFF'}</b> |
    Threat Modeling: <b>{'ON' if adversary_simulation else 'OFF'}</b> |
    GNSS v2: <b>{'PRIMARY' if gnss_denied_navigation_v2 else 'OFF'}</b>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

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
        sensor_band = st.selectbox('Sensor Band', ['EO', 'MWIR', 'LWIR'])
        sensor_quality = st.slider('Sensor Quality Factor', 0.5, 1.5, 1.0, 0.05)
        loiter_minutes = st.slider('Loiter Duration (min)', 0, 60, 0)
        include_rtb = st.checkbox('Include RTB Phase', value=False)
        adversary_radar_density = st.slider('Radar Zone Density', 0.0, 1.0, 0.3, 0.05)
        adversary_ir_density = st.slider('IR Tracker Density', 0.0, 1.0, 0.3, 0.05)
        adversary_jammer_density = st.slider('Jammer Density', 0.0, 1.0, 0.2, 0.05)
        radar_frequency_ghz = st.slider('Radar Frequency (GHz)', 1.0, 18.0, 10.0, 0.5)
        radar_tx_power_kw = st.slider('Radar TX Power (kW)', 1.0, 200.0, 40.0, 1.0)
        fusion_quality = st.slider('Sensor Fusion Quality', 0.5, 1.5, 1.0, 0.05)
        drift_sensitivity = st.slider('Drift Sensitivity', 0.5, 1.5, 1.0, 0.05)
        map_uncertainty_factor = st.slider('Map Uncertainty Factor', 0.0, 1.0, 0.25, 0.05)
        gnss_update_gain = st.slider('GNSS v2 Update Gain', 0.2, 0.9, 0.55, 0.05)
        battery_cycle_count = st.slider('Battery Cycle Count', 0, 1000, 120, 10)
        battery_internal_resistance_mohm = st.slider('Battery Internal Resistance (mΩ)', 5.0, 120.0, 28.0, 1.0)
        battery_nominal_voltage_v = st.slider('Battery Nominal Voltage (V)', 12.0, 60.0, 22.2, 0.1)
        engine_wear_factor = st.slider('Engine Wear Factor', 0.8, 1.2, 1.0, 0.05)
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

            autopilot_profile = run_detectability_autopilot(
                enabled=detectability_autopilot,
                overall_score=overall_score,
                visual_score=visual_score,
                thermal_score=thermal_score,
                confidence=detect_confidence,
                altitude_m=altitude_m,
                speed_kmh=flight_speed_kmh,
                power_system=profile['power_system'],
                hybrid_assist_enabled=(profile['power_system'] == 'ICE'),
                stealth_drag_penalty=stealth_drag_penalty,
            )
            render_detectability_autopilot_panel(autopilot_profile)

            route_optimization_profile = optimize_route_profile(
                enabled=route_optimization,
                waypoints=waypoints,
                speed_kmh=float(autopilot_profile.get('target_speed_kmh', flight_speed_kmh)),
                altitude_m=int(autopilot_profile.get('target_altitude_m', altitude_m)),
                overall_detectability=overall_score,
                visual_detectability=visual_score,
                thermal_detectability=thermal_score,
                terrain_penalty=terrain_penalty,
                stealth_drag_penalty=stealth_drag_penalty,
                threat_zone_km=threat_zone_km if 'threat_zone_km' in locals() else 5.0,
            )
            render_route_optimization_panel(route_optimization_profile)

            terrain_masking_profile = estimate_terrain_masking(
                enabled=(terrain_masking_v2 if 'terrain_masking_v2' in locals() else terrain_masking),
                waypoints=waypoints,
                altitude_m=int(route_optimization_profile.get('recommended_altitude_m', altitude_m)),
                terrain_penalty=terrain_penalty,
                cloud_cover=cloud_cover,
                overall_detectability=overall_score,
                visual_detectability=visual_score,
                thermal_detectability=thermal_score,
                threat_zone_km=threat_zone_km if 'threat_zone_km' in locals() else 5.0,
                terrain_ridge_amplitude_m=terrain_ridge_amplitude_m if 'terrain_ridge_amplitude_m' in locals() else 80.0,
            )
            render_terrain_masking_panel(terrain_masking_profile)

            sensor_model_profile = compute_sensor_model(
                enabled=sensor_modeling,
                sensor_band=sensor_band,
                sensor_quality=sensor_quality,
                humidity_factor=humidity_factor,
                cloud_cover=cloud_cover,
                altitude_m=int(route_optimization_profile.get('recommended_altitude_m', altitude_m)),
                visual_score=visual_score,
                thermal_score=thermal_score,
                overall_score=overall_score,
                delta_t=delta_t,
            )
            render_sensor_modeling_panel(sensor_model_profile)


            st.subheader('Detectability AI Suggestions')
            det_suggestions = detectability_ai_suggestions(
                visual_score=visual_score,
                thermal_score=thermal_score,
                overall_score=overall_score,
                confidence=detect_confidence,
                altitude_m=altitude_m,
                speed_kmh=flight_speed_kmh,
                cloud_cover=cloud_cover,
                gustiness=gustiness,
                stealth_factor=stealth_drag_penalty,
                power_system=profile['power_system'],
                delta_T=delta_T,
            )
            for level, msg in det_suggestions:
                if level == 'error':
                    st.error(msg)
                elif level == 'warning':
                    st.warning(msg)
                elif level == 'success':
                    st.success(msg)
                else:
                    st.info(msg)

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

        detectability_color = '#22c55e' if overall_score < 33 else '#f59e0b' if overall_score < 67 else '#ef4444'
        st.markdown(
            render_mission_hero(
                endurance_min=flight_time_minutes,
                total_distance_km=total_distance_km,
                best_range_km=best_km,
                detectability_label=('LOW' if overall_score < 33 else 'MODERATE' if overall_score < 67 else 'HIGH'),
                detectability_color=detectability_color,
                power_system=profile['power_system'],
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
        mission_profile = {
            'phases': [],
            'total_time_min': 0.0,
            'total_energy_Wh': 0.0,
            'total_fuel_L': 0.0,
            'remaining_energy_Wh': None,
            'remaining_fuel_L': None,
        }

        try:
            mission_profile = simulate_mission_phases(
                profile=profile,
                payload_weight_g=payload_weight_g,
                cruise_speed_kmh=flight_speed_kmh,
                wind_speed_kmh=wind_speed_kmh,
                temperature_c=temperature_c,
                cruise_altitude_m=altitude_m,
                elevation_gain_m=elevation_gain_m,
                gustiness=gustiness,
                terrain_penalty=terrain_penalty,
                stealth_drag_penalty=stealth_drag_penalty,
                battery_capacity_wh=(result.get('battery_derated_Wh') if profile['power_system'] == 'Battery' else None),
                fuel_tank_l=(result.get('usable_fuel_L') if profile['power_system'] == 'ICE' else None),
                loiter_minutes=float(loiter_minutes),
                include_rtb=include_rtb,
            )
            render_mission_phase_panel(mission_profile, profile['power_system'])
        except Exception as phase_err:
            st.warning('Mission Phase Simulation could not be generated for this run.')
            if debug_mode:
                st.exception(phase_err)


        scenario_base_inputs = {
            'payload_weight_g': payload_weight_g,
            'flight_speed_kmh': flight_speed_kmh,
            'wind_speed_kmh': wind_speed_kmh,
            'temperature_c': temperature_c,
            'altitude_m': altitude_m,
            'elevation_gain_m': elevation_gain_m,
            'flight_mode': flight_mode,
            'gustiness': gustiness,
            'terrain_penalty': terrain_penalty,
            'terrain_ridge_amplitude_m': terrain_ridge_amplitude_m if 'terrain_ridge_amplitude_m' in locals() else 80.0,
            'stealth_drag_penalty': stealth_drag_penalty,
            'battery_capacity_wh': battery_capacity_wh if 'battery_capacity_wh' in locals() else 0.0,
            'fuel_tank_l': fuel_tank_l if 'fuel_tank_l' in locals() and fuel_tank_l is not None else profile.get('fuel_tank_l', 0.0),
            'cloud_cover': cloud_cover,
            'humidity_factor': humidity_factor,
            'background_complexity': background_complexity,
            'effective_size_m': effective_size_m,
            'waypoints': waypoints,
            'loiter_minutes': float(loiter_minutes),
            'include_rtb': include_rtb,
            'threat_zone_km': threat_zone_km if 'threat_zone_km' in locals() else 5.0,
            'sensor_band': sensor_band,
            'sensor_quality': sensor_quality,
            'adversary_radar_density': adversary_radar_density,
            'adversary_ir_density': adversary_ir_density,
            'adversary_jammer_density': adversary_jammer_density,
            'radar_frequency_ghz': radar_frequency_ghz,
            'radar_tx_power_kw': radar_tx_power_kw,
            'fusion_quality': fusion_quality if 'fusion_quality' in locals() else 1.0,
            'drift_sensitivity': drift_sensitivity if 'drift_sensitivity' in locals() else 1.0,
            'map_uncertainty_factor': map_uncertainty_factor if 'map_uncertainty_factor' in locals() else 0.25,
            'gnss_update_gain': gnss_update_gain if 'gnss_update_gain' in locals() else 0.55,
        }
        scenario_comparison_results = render_scenario_comparison_panel(
            enabled=scenario_comparison_engine,
            profile=profile,
            base_inputs=scenario_base_inputs,
        )

        detail = {'drone_model': drone_model, 'type': profile['type'], 'power_system': profile['power_system'], 'payload_g': payload_weight_g, 'total_mass_kg': round(total_weight_kg, 3), 'weight_N': round(weight_N, 2), 'flight_speed_kmh': round(flight_speed_kmh, 2), 'effective_speed_ms': round(result.get('V_effective_ms', V_ms), 3), 'wind_speed_kmh': round(wind_speed_kmh, 2), 'wind_speed_ms': round(W_ms, 3), 'altitude_m': altitude_m, 'temperature_C': temperature_c, 'flight_mode': flight_mode, 'rho': round(rho, 4), 'rho_ratio': round(rho_ratio, 4), 'gustiness': gustiness, 'terrain_factor': round(terrain_penalty, 3), 'stealth_drag_factor': round(stealth_drag_penalty, 3), 'wind_penalty_pct': round(wind_penalty_pct, 2), 'thermal_load_deltaT_estimate_C': round(delta_T, 2), 'dispatch_endurance_min': round(flight_time_minutes, 2), 'total_distance_km': round(total_distance_km, 2), 'best_heading_range_km': round(best_km, 2), 'upwind_range_km': round(worst_km, 2), 'visual_heuristic_score_0_100': round(visual_score, 1), 'thermal_heuristic_score_0_100': round(thermal_score, 1), 'blended_detectability_score_0_100': round(overall_score, 1), 'heuristic_confidence_0_100': round(detect_confidence, 1), 'detectability_overall': 'LOW' if overall_kind == 'success' else 'MODERATE' if overall_kind == 'warning' else 'HIGH'}

        detail['autopilot_target_speed_kmh'] = round(float(autopilot_profile.get('target_speed_kmh', flight_speed_kmh)), 2)
        detail['autopilot_target_altitude_m'] = int(autopilot_profile.get('target_altitude_m', altitude_m))
        detail['autopilot_hybrid_assist_recommend'] = bool(autopilot_profile.get('hybrid_assist_recommend', False))
        detail['autopilot_active'] = bool(autopilot_profile.get('active', False))
        detail['route_optimization_active'] = bool(route_optimization_profile.get('active', False))
        detail['route_base_score'] = round(float(route_optimization_profile.get('base_score', 0.0)), 2)
        detail['route_optimized_score'] = round(float(route_optimization_profile.get('optimized_score', 0.0)), 2)
        detail['route_recommended_speed_kmh'] = round(float(route_optimization_profile.get('recommended_speed_kmh', flight_speed_kmh)), 2)
        detail['route_recommended_altitude_m'] = int(route_optimization_profile.get('recommended_altitude_m', altitude_m))
        detail['terrain_masking_active'] = bool(terrain_masking_profile.get('active', False))
        detail['terrain_masking_score'] = round(float(terrain_masking_profile.get('masking_score', 0.0)), 1)
        detail['terrain_adjusted_visual_score'] = round(float(terrain_masking_profile.get('adjusted_visual_score', visual_score)), 1)
        detail['terrain_adjusted_overall_score'] = round(float(terrain_masking_profile.get('adjusted_overall_score', overall_score)), 1)
        detail['terrain_los_block_fraction'] = round(float(terrain_masking_profile.get('los_block_fraction', 0.0)), 3)
        detail['terrain_shadowed_distance_km'] = round(float(terrain_masking_profile.get('shadowed_distance_km', 0.0)), 3)
        detail['sensor_modeling_enabled'] = bool(sensor_modeling)
        detail['sensor_band'] = sensor_band
        detail['sensor_quality'] = round(float(sensor_quality), 2)
        detail['sensor_max_likely_detection_km'] = round(float(sensor_model_profile.get('max_likely_detection_km', 0.0)), 2)
        detail['sensor_baseline_detection_probability_pct'] = round(float(sensor_model_profile.get('baseline_probability', 0.0)), 1)
        if 'swarm_intel_profile' in locals():
            detail['swarm_intelligence_score'] = round(float(swarm_intel_profile.get('swarm_score', 0.0)), 1)
            detail['swarm_resilience_score'] = round(float(swarm_intel_profile.get('resilience_score', 0.0)), 1)
        # Mission Phase Summary (safe ordering)
        if 'mission_profile' in locals():
            detail.update({
                'phase_total_time_min': round(mission_profile.get('total_time_min', 0.0), 2),
                'phase_count': len(mission_profile.get('phases', [])),
            })
            if profile['power_system'] == 'Battery':
                detail['phase_total_energy_Wh'] = round(mission_profile.get('total_energy_Wh', 0.0), 2)
                detail['phase_remaining_energy_Wh'] = round(float(mission_profile.get('remaining_energy_Wh') or 0.0), 2)
            else:
                detail['phase_total_fuel_L'] = round(mission_profile.get('total_fuel_L', 0.0), 3)
                detail['phase_remaining_fuel_L'] = round(float(mission_profile.get('remaining_fuel_L') or 0.0), 3)

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
            f"- **Mission phase total time**: {mission_profile.get('total_time_min', 0.0):.1f} min across {len(mission_profile.get('phases', []))} phases",
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

        tactical_params = {
            'drone': drone_model,
            'power_system': profile['power_system'],
            'flight_mode': flight_mode,
            'altitude_m': altitude_m,
            'speed_kmh': flight_speed_kmh,
            'cloud_cover': cloud_cover,
            'visual_score': visual_score,
            'thermal_score': thermal_score,
            'overall_score': overall_score,
            'endurance_min': flight_time_minutes,
            'loiter_minutes': float(loiter_minutes),
            'include_rtb': bool(include_rtb),
            'hybrid_possible': bool(profile['power_system'] == 'ICE'),
            'autopilot_target_speed_kmh': float(autopilot_profile.get('target_speed_kmh', flight_speed_kmh)) if 'autopilot_profile' in locals() else float(flight_speed_kmh),
            'autopilot_target_altitude_m': float(autopilot_profile.get('target_altitude_m', altitude_m)) if 'autopilot_profile' in locals() else float(altitude_m),
            'sensor_max_likely_detection_km': float(sensor_model_profile.get('max_likely_detection_km', 0.0)) if 'sensor_model_profile' in locals() else 0.0,
            'terrain_masking_score': float(terrain_masking_profile.get('masking_score', 0.0)) if 'terrain_masking_profile' in locals() else 0.0,
            'mission_feasible': bool(mission_profile.get('mission_feasible', True)) if isinstance(mission_profile, dict) else True,
            'radar_detect_probability_pct': float(adversary_profile.get('radar_detection_probability_pct', 0.0)) if 'adversary_profile' in locals() else 0.0,
            'adversary_posture': adversary_profile.get('recommended_posture', 'Nominal') if 'adversary_profile' in locals() else 'Nominal',
            'allowed_loiter_min': float(coupled_loiter_profile.get('allowed_loiter_min', loiter_minutes)) if 'coupled_loiter_profile' in locals() else float(loiter_minutes),
        }
        tactical_briefing = generate_tactical_briefing(
            llm_enabled=OPENAI_AVAILABLE,
            tactical_mode_enabled=llm_tactical_mode,
            params=tactical_params,
        )
        render_tactical_briefing_panel(tactical_briefing)

        adversary_profile = compute_adversary_simulation(
            enabled=adversary_simulation,
            radar_density=adversary_radar_density,
            ir_density=adversary_ir_density,
            jammer_density=adversary_jammer_density,
            altitude_m=int(route_optimization_profile.get('recommended_altitude_m', altitude_m)) if 'route_optimization_profile' in locals() else altitude_m,
            speed_kmh=float(autopilot_profile.get('target_speed_kmh', flight_speed_kmh)) if 'autopilot_profile' in locals() else flight_speed_kmh,
            overall_detectability=float(terrain_masking_profile.get('adjusted_overall_score', overall_score)) if 'terrain_masking_profile' in locals() else overall_score,
            visual_score=float(terrain_masking_profile.get('adjusted_visual_score', visual_score)) if 'terrain_masking_profile' in locals() else visual_score,
            thermal_score=thermal_score,
            sensor_detection_range_km=float(sensor_model_profile.get('max_likely_detection_km', 0.0)) if 'sensor_model_profile' in locals() else 0.0,
            terrain_masking_score=float(terrain_masking_profile.get('masking_score', 0.0)) if 'terrain_masking_profile' in locals() else 0.0,
            route_score=float(route_optimization_profile.get('optimized_score', 0.0)) if 'route_optimization_profile' in locals() else 0.0,
            threat_zone_km=threat_zone_km if 'threat_zone_km' in locals() else 5.0,
            power_system=profile['power_system'],
            radar_frequency_ghz=radar_frequency_ghz if 'radar_frequency_ghz' in locals() else 10.0,
            radar_tx_power_kw=radar_tx_power_kw if 'radar_tx_power_kw' in locals() else 40.0,
            effective_size_m=effective_size_m if 'effective_size_m' in locals() else 1.0,
        )
        render_adversary_simulation_panel(adversary_profile)
        route_optimization_profile = optimize_route_profile(
            enabled=route_optimization,
            waypoints=waypoints,
            speed_kmh=float(autopilot_profile.get('target_speed_kmh', flight_speed_kmh)),
            altitude_m=int(autopilot_profile.get('target_altitude_m', altitude_m)),
            overall_detectability=overall_score,
            visual_detectability=visual_score,
            thermal_detectability=thermal_score,
            terrain_penalty=terrain_penalty,
            stealth_drag_penalty=stealth_drag_penalty,
            threat_zone_km=threat_zone_km if 'threat_zone_km' in locals() else 5.0,
            radar_threat_penalty=float(adversary_profile.get('radar_risk', 0.0)) * 0.20,
        )
        coupled_loiter_profile = compute_coupled_loiter_feasibility(
            requested_loiter_min=float(loiter_minutes),
            radar_detect_probability_pct=float(adversary_profile.get('radar_detection_probability_pct', 0.0)),
            combined_threat_score=float(adversary_profile.get('combined_threat_score', 0.0)),
            route_mode=str(route_optimization_profile.get('recommended_route_mode', 'Direct')),
        )
        render_coupled_threat_panel(coupled_loiter_profile)

        nav_profile_v2 = compute_gnss_denied_navigation_v2(
            enabled=(gnss_denied_navigation_v2 if 'gnss_denied_navigation_v2' in locals() else gnss_denied_navigation),
            fusion_quality=fusion_quality,
            drift_sensitivity=drift_sensitivity,
            map_uncertainty_factor=map_uncertainty_factor,
            update_gain=gnss_update_gain if 'gnss_update_gain' in locals() else 0.55,
            flight_time_minutes=flight_time_minutes,
            total_distance_km=total_distance_km,
            speed_kmh=float(autopilot_profile.get('target_speed_kmh', flight_speed_kmh)) if 'autopilot_profile' in locals() else flight_speed_kmh,
            terrain_masking_score=float(terrain_masking_profile.get('masking_score', 0.0)) if 'terrain_masking_profile' in locals() else 0.0,
            jammer_risk=float(adversary_profile.get('jammer_risk', 0.0)) if 'adversary_profile' in locals() else 0.0,
            route_score=float(route_optimization_profile.get('optimized_score', 0.0)) if 'route_optimization_profile' in locals() else 0.0,
            waypoints=waypoints,
        )
        render_gnss_denied_navigation_v2_panel(nav_profile_v2)

        if show_validation:
            st.subheader('Model Validation')
            st.caption('Nominal-condition comparison against reference endurance targets.')
            st.dataframe(pd.DataFrame(validation_report()), use_container_width=True)

        st.subheader('Export Scenario Summary')
        results_summary = {'Drone Model': drone_model, 'Power System': profile['power_system'], 'Type': profile['type'], 'Flight Mode': flight_mode, 'Payload (g)': int(payload_weight_g), 'Speed (km/h)': float(flight_speed_kmh), 'Wind (km/h)': float(wind_speed_kmh), 'Gustiness (0-10)': int(gustiness), 'Altitude (m)': int(altitude_m), 'Temperature (C)': float(temperature_c), 'Air Density (kg/m^3)': round(rho, 3), 'Density Ratio (rho/rho0)': round(rho_ratio, 3), 'Wind Penalty (%)': round(wind_penalty_pct, 2), 'Dispatchable Endurance (min)': round(flight_time_minutes, 2), 'Total Distance (km)': round(total_distance_km, 2), 'Best Heading Range (km)': round(best_km, 2), 'Upwind Range (km)': round(worst_km, 2), 'Thermal Signature Risk': ('Low' if delta_T < 10 else 'Moderate' if delta_T < 20 else 'High'),
            'ΔT (C)': round(delta_T, 2), 'Visual Heuristic Score (0-100)': round(visual_score, 1), 'Thermal Heuristic Score (0-100)': round(thermal_score, 1), 'Blended Detectability Score (0-100)': round(overall_score, 1), 'Heuristic Confidence (0-100)': round(detect_confidence, 1), 'Overall Detectability': detail['detectability_overall'], 'Mission Phase Total Time (min)': round(mission_profile.get('total_time_min', 0.0), 2), 'Mission Phase Count': len(mission_profile.get('phases', [])), 'Autopilot Active': bool(autopilot_profile.get('active', False)), 'Autopilot Target Speed (km/h)': round(float(autopilot_profile.get('target_speed_kmh', flight_speed_kmh)), 2), 'Autopilot Target Altitude (m)': int(autopilot_profile.get('target_altitude_m', altitude_m)), 'Route Optimization Active': bool(route_optimization_profile.get('active', False)), 'Route Base Score': round(float(route_optimization_profile.get('base_score', 0.0)), 2), 'Route Optimized Score': round(float(route_optimization_profile.get('optimized_score', 0.0)), 2), 'Terrain Masking Score': round(float(terrain_masking_profile.get('masking_score', 0.0)), 1), 'Terrain Adjusted Overall Score': round(float(terrain_masking_profile.get('adjusted_overall_score', overall_score)), 1), 'Terrain LOS Block Fraction': round(float(terrain_masking_profile.get('los_block_fraction', 0.0)), 3), 'Terrain Shadowed Distance (km)': round(float(terrain_masking_profile.get('shadowed_distance_km', 0.0)), 3), 'Swarm Intelligence Score': round(float(swarm_intel_profile.get('swarm_score', 0.0)), 1) if 'swarm_intel_profile' in locals() else 0.0, 'Swarm Resilience Score': round(float(swarm_intel_profile.get('resilience_score', 0.0)), 1) if 'swarm_intel_profile' in locals() else 0.0}
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
