# UAV Battery Efficiency Estimator | v0.8.4 aircraft chase camera + battery Plotly twins
# Standalone Streamlit application | Built by Tareq Omrani
# requirements.txt: streamlit>=1.40,<2; numpy>=1.26,<3; pandas>=2,<4;
# plotly>=5.20,<8; pyarrow<25
#
# Engineering research simulator. Not an aircraft-qualified flight model,
# battery management system, autopilot, or safety-critical control system.
# GPT mission interpretation and PX4/ArduPilot control are NOT implemented.
from __future__ import annotations

import io
import json
import math
import zipfile
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

VERSION = "0.8.4"
G = 9.80665
R_AIR = 287.05
P_SL = 101325.0
LAPSE = 0.0065


def clamp(x, low, high):
    return max(low, min(high, float(x)))


def clamp01(x):
    return clamp(x, 0.0, 1.0)


# Aircraft reference data are ILLUSTRATIVE research inputs, not manufacturer-
# verified performance data. In battery profiles, base mass includes reference
# battery. For ICE aircraft, base mass excludes mission fuel.
UAV_PROFILES: Dict[str, Dict[str, Any]] = {
    "Generic Quad": dict(type="rotor", power_system="Battery", base_weight_kg=1.2,
        max_payload_g=800, battery_wh=60., draw_watt=150., hover_power_W_ref=150.,
        rotor_WL_proxy=45., parasitic_area_m2=.025, cd_body=1., surface_area_m2=.20,
        ai_capabilities="Basic stabilization and waypoint navigation"),
    "DJI Phantom": dict(type="rotor", power_system="Battery", base_weight_kg=1.4,
        max_payload_g=500, battery_wh=68., draw_watt=140., hover_power_W_ref=140.,
        rotor_WL_proxy=50., parasitic_area_m2=.024, cd_body=1., surface_area_m2=.22,
        ai_capabilities="Object tracking and return-to-home concepts"),
    "Skydio 2+": dict(type="rotor", power_system="Battery", base_weight_kg=.8,
        max_payload_g=150, battery_wh=45., draw_watt=95., hover_power_W_ref=95.,
        rotor_WL_proxy=40., parasitic_area_m2=.018, cd_body=1., surface_area_m2=.15,
        ai_capabilities="Visual navigation and obstacle avoidance concepts"),
    "Freefly Alta 8": dict(type="rotor", power_system="Battery", base_weight_kg=6.2,
        max_payload_g=9000, battery_wh=710., draw_watt=900., hover_power_W_ref=900.,
        rotor_WL_proxy=60., parasitic_area_m2=.08, cd_body=1.1, surface_area_m2=.60,
        ai_capabilities="Autonomous payload positioning concepts"),
    "Teal 2 / Golden Eagle": dict(type="rotor", power_system="Battery", base_weight_kg=1.25,
        max_payload_g=300, battery_wh=110., draw_watt=180., hover_power_W_ref=180.,
        rotor_WL_proxy=46., parasitic_area_m2=.020, cd_body=1., surface_area_m2=.18,
        ai_capabilities="Edge perception and GNSS-denied operation concepts"),
    "RQ-11 Raven": dict(type="fixed", power_system="Battery", base_weight_kg=1.9,
        max_payload_g=300, battery_wh=120., draw_watt=90., wing_area_m2=.24,
        wingspan_m=1.4, cd0=.040, oswald_e=.78, prop_eff=.72, hotel_W=8.,
        surface_area_m2=.22, cl_max=1.3,
        ai_capabilities="Stabilized flight and route autonomy concepts"),
    "RQ-20 Puma": dict(type="fixed", power_system="Battery", base_weight_kg=6.3,
        max_payload_g=600, battery_wh=700., draw_watt=180., wing_area_m2=.55,
        wingspan_m=2.8, cd0=.038, oswald_e=.80, prop_eff=.75, hotel_W=12.,
        surface_area_m2=.45, cl_max=1.4,
        ai_capabilities="Route planning and autonomous loiter concepts"),
    "Quantum Systems Vector": dict(type="fixed", power_system="Battery", base_weight_kg=8.0,
        max_payload_g=1500, battery_wh=1200., draw_watt=300., wing_area_m2=.90,
        wingspan_m=2.8, cd0=.035, oswald_e=.82, prop_eff=.78, hotel_W=20.,
        surface_area_m2=.55, cl_max=1.5,
        ai_capabilities="Edge sensing and geospatial mission planning concepts"),
    "Vector AI (Fixed-Wing)": dict(type="fixed", power_system="Battery", base_weight_kg=8.0,
        max_payload_g=1500, battery_wh=1200., draw_watt=300., wing_area_m2=.90,
        wingspan_m=2.8, cd0=.035, oswald_e=.82, prop_eff=.78, hotel_W=20.,
        surface_area_m2=.55, cl_max=1.5,
        ai_capabilities="Experimental onboard intelligence and route planning"),
    "Vector AI (Multicopter)": dict(type="rotor", power_system="Battery", base_weight_kg=8.0,
        max_payload_g=1500, battery_wh=1200., draw_watt=1200., hover_power_W_ref=1200.,
        rotor_WL_proxy=65., parasitic_area_m2=.10, cd_body=1.1, surface_area_m2=.60,
        ai_capabilities="VTOL mode and confined-area operations concepts"),
    "MQ-1 Predator": dict(type="fixed", power_system="ICE", base_weight_kg=512.,
        max_payload_g=204000, battery_wh=150., draw_watt=650., wing_area_m2=11.5,
        wingspan_m=14.8, cd0=.025, oswald_e=.80, prop_eff=.80, hotel_W=400.,
        surface_area_m2=5., cl_max=1.5, bsfc_gpkwh=260., fuel_density_kgpl=.72,
        fuel_tank_l=300., max_shaft_power_w=86000.,
        ai_capabilities="Surveillance and mission planning concepts"),
    "MQ-9 Reaper": dict(type="fixed", power_system="ICE", base_weight_kg=2223.,
        max_payload_g=1700000, battery_wh=200., draw_watt=800., wing_area_m2=24.,
        wingspan_m=20., cd0=.030, oswald_e=.85, prop_eff=.82, hotel_W=700.,
        surface_area_m2=8., cl_max=1.6, bsfc_gpkwh=330., fuel_density_kgpl=.80,
        fuel_tank_l=900., max_shaft_power_w=671000.,
        ai_capabilities="Sensor fusion and autonomous monitoring concepts"),
    "Custom Build": dict(type="rotor", power_system="Battery", base_weight_kg=2.,
        max_payload_g=1500, battery_wh=150., draw_watt=220., hover_power_W_ref=220.,
        rotor_WL_proxy=50., parasitic_area_m2=.03, cd_body=1., surface_area_m2=.25,
        ai_capabilities="Experimental user-configured system"),
}
DEFAULT_SPEED_KMH = {
    "Generic Quad":25, "DJI Phantom":35, "Skydio 2+":30, "Freefly Alta 8":25,
    "Teal 2 / Golden Eagle":50, "RQ-11 Raven":45, "RQ-20 Puma":60,
    "Quantum Systems Vector":70, "Vector AI (Fixed-Wing)":70,
    "Vector AI (Multicopter)":30, "MQ-1 Predator":140, "MQ-9 Reaper":180,
    "Custom Build":30,
}
DEFAULT_SIZE_M = {
    "Generic Quad":.45, "DJI Phantom":.35, "Skydio 2+":.30,
    "Freefly Alta 8":1.3, "Teal 2 / Golden Eagle":.50,
    "RQ-11 Raven":1.4, "RQ-20 Puma":2.8, "Quantum Systems Vector":2.8,
    "Vector AI (Fixed-Wing)":2.8, "Vector AI (Multicopter)":2.2,
    "MQ-1 Predator":14.8, "MQ-9 Reaper":20., "Custom Build":1.,
}


def battery_mass_kg(wh, specific_energy_whkg):
    return float(wh) / max(50., float(specific_energy_whkg))


def infer_series_cells(wh):
    return 4 if wh <= 80 else (6 if wh <= 180 else 12)


def atmosphere_state(altitude_m, sea_level_temp_c=15.):
    # Tropospheric approximation, used only up to 11 km.
    h = clamp(altitude_m, 0., 11000.)
    t0 = float(sea_level_temp_c) + 273.15
    temp_k = max(180., t0 - LAPSE * h)
    p = P_SL * (temp_k / t0) ** (G / (R_AIR * LAPSE))
    return p / (R_AIR * temp_k), temp_k - 273.15, p


def qnormalize(q):
    q = np.asarray(q, float)
    norm = np.linalg.norm(q)
    return q / norm if norm > 1e-12 else np.array([1.,0.,0.,0.])


def q_from_euler(roll, pitch, yaw):
    cr,sr=math.cos(roll/2),math.sin(roll/2)
    cp,sp=math.cos(pitch/2),math.sin(pitch/2)
    cy,sy=math.cos(yaw/2),math.sin(yaw/2)
    return qnormalize([cr*cp*cy+sr*sp*sy, sr*cp*cy-cr*sp*sy,
                       cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy])


def euler_from_q(q):
    w,x,y,z = qnormalize(q)
    roll=math.atan2(2*(w*x+y*z),1-2*(x*x+y*y))
    sp=clamp(2*(w*y-z*x),-1.,1.)
    pitch=math.asin(sp)
    yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
    return roll,pitch,yaw


def body_to_ned(q):
    w,x,y,z=qnormalize(q)
    return np.array([
        [1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y)],
        [2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x)],
        [2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)],
    ])


def q_derivative(q,p,rate_q,r):
    w,x,y,z=qnormalize(q)
    return .5*np.array([-x*p-y*rate_q-z*r,
        w*p+y*r-z*rate_q, w*rate_q-x*r+z*p, w*r+x*rate_q-y*p])


def q_integrate(q,p,rate_q,r,dt):
    q=qnormalize(q)
    mid=qnormalize(q+.5*dt*q_derivative(q,p,rate_q,r))
    return qnormalize(q+dt*q_derivative(mid,p,rate_q,r))


@dataclass
class Environment:
    density:float=1.225
    temperature_c:float=15.
    pressure_pa:float=P_SL
    wind_n:float=0.
    wind_e:float=0.
    wind_d:float=0.


@dataclass
class DynamicsParams:
    kind:str
    mass_reference:float
    ix:float
    iy:float
    iz:float
    area:float
    span:float
    chord:float
    rotor_disk_area:float
    max_roll_moment:float
    max_pitch_moment:float
    max_yaw_moment:float
    cl0:float=.25
    cl_alpha:float=4.8
    cl_q:float=3.5
    cl_de:float=.55
    cd0:float=.035
    induced_k:float=.055
    cy_beta:float=-.65
    cy_da:float=.05
    cy_dr:float=.20
    cl_beta:float=-.10
    cl_p:float=-.45
    cl_r:float=.12
    cl_da:float=.18
    cl_dr:float=.08
    cm0:float=.03
    cm_alpha:float=-1.05
    cm_q:float=-7.
    cm_de:float=-1.15
    cn_beta:float=.16
    cn_p:float=-.06
    cn_r:float=-.22
    cn_da:float=.02
    cn_dr:float=-.12
    alpha_stall_deg:float=16.
    cl_max:float=1.45
    rotor_drag_area:float=.03


def build_dynamics_params(profile, mass):
    m=max(.1,float(mass))
    if profile['type']=='fixed':
        area=max(.08,float(profile.get('wing_area_m2',.5)))
        span=max(.4,float(profile.get('wingspan_m',2.)))
        chord=area/span
        aspect_ratio=span*span/area
        oswald=clamp(profile.get('oswald_e',.8),.3,.95)
        return DynamicsParams('fixed',m, max(.02,.055*m*span**2),
            max(.03,.08*m*(.55*span)**2), max(.03,.095*m*span**2),
            area,span,chord,0.,.12*m*G*span,.10*m*G*chord,.06*m*G*span,
            cd0=float(profile.get('cd0',.035)),induced_k=1/(math.pi*oswald*aspect_ratio),
            alpha_stall_deg=float(profile.get('alpha_stall_deg',16.)),
            cl_max=float(profile.get('cl_max',1.45)))
    c=max(.25,.22*math.sqrt(m)+.25)
    disk=max(.03,float(profile['base_weight_kg'])*G/max(20.,profile.get('rotor_WL_proxy',45.)))
    return DynamicsParams('rotor',m,max(.015,.18*m*c*c),max(.015,.18*m*c*c),
        max(.02,.30*m*c*c),c*c,2*c,c,disk,.35*m*G*c,.35*m*G*c,.12*m*G*c,
        rotor_drag_area=max(.005,float(profile.get('parasitic_area_m2',.03))*float(profile.get('cd_body',1.))))


ALPHA_GRID=np.array([-90,-70,-50,-35,-25,-20,-15,-10,-5,0,5,10,15,20,25,35,50,70,90.])


def aero_coefficients(alpha_deg, p):
    alpha=math.radians(clamp(alpha_deg,-90.,90.))
    stall=math.radians(p.alpha_stall_deg)
    attached_cl=p.cl_max*math.tanh((p.cl0+p.cl_alpha*alpha)/p.cl_max)
    attached_cd=p.cd0+p.induced_k*attached_cl**2
    separated_cl=1.10*math.sin(2*alpha)
    separated_cd=.10+1.35*math.sin(alpha)**2
    start=.85*stall
    end=max(start+math.radians(8.),1.45*stall)
    blend=clamp01((abs(alpha)-start)/(end-start))
    cl=(1-blend)*attached_cl+blend*separated_cl
    cd=(1-blend)*attached_cd+blend*separated_cd
    cm=(1-blend)*(p.cm0+p.cm_alpha*alpha)+blend*clamp(-.35*math.sin(alpha),-.35,.35)
    return cl,cd,cm


def aerodynamic_table(p):
    arr=np.array([aero_coefficients(a,p) for a in ALPHA_GRID])
    return pd.DataFrame({'alpha_deg':ALPHA_GRID,'CL':arr[:,0],'CD':arr[:,1],'Cm':arr[:,2]})


@dataclass
class Trim:
    alpha_deg:float=0.
    elevator:float=0.
    throttle:float=.5
    drag_n:float=0.
    shaft_required_w:float=0.
    converged:bool=True
    power_feasible:bool=True


def solve_trim(p,profile,rho,speed,mass,max_shaft):
    if p.kind=='rotor':
        weight=mass*G
        shaft=weight**1.5/(.72*math.sqrt(2*max(.2,rho)*max(.03,p.rotor_disk_area)))
        return Trim(0.,0.,clamp(shaft/max(1.,max_shaft),.0,1.),0.,shaft,
                    True,shaft<=max_shaft)
    v=max(4.,speed)
    qbar=.5*max(.2,rho)*v*v
    weight=mass*G
    def residual(alpha_deg):
        cl,cd,cm=aero_coefficients(alpha_deg,p)
        elevator=clamp(-cm/p.cm_de,-.65,.65)
        lift=qbar*p.area*(cl+p.cl_de*elevator)
        return lift-weight,elevator,cd+.012*elevator**2
    low,high=-3.,min(p.alpha_stall_deg-1.5,13.5)
    rlow,rhigh=residual(low)[0],residual(high)[0]
    converged=rlow*rhigh<=0
    if converged:
        for _ in range(55):
            mid=(low+high)/2
            rm=residual(mid)[0]
            if rlow*rm<=0: high=mid
            else: low=mid;rlow=rm
        alpha=(low+high)/2
    else:
        candidates=np.linspace(low,high,100)
        alpha=float(min(candidates,key=lambda a: abs(residual(a)[0])))
    _,elevator,cd=residual(alpha)
    drag=qbar*p.area*cd
    shaft=drag*v/max(.3,float(profile.get('prop_eff',.72)))
    return Trim(alpha,elevator,clamp(shaft/max(1.,max_shaft),0.,1.),
                drag,shaft,converged,shaft<=max_shaft)


@dataclass
class BatterySnapshot:
    soc:float
    soh:float
    nominal_wh:float
    temp_adjusted_wh:float
    soh_adjusted_wh:float
    usable_capacity_wh:float
    remaining_wh:float
    ocv_v:float
    terminal_v:float
    current_a:float
    c_rate:float
    r0_ohm:float
    polarization_v:float
    demanded_w:float
    delivered_w:float
    limit_w:float
    limited:bool
    temperature_c:float
    heat_w:float
    min_cell_v:float
    max_cell_v:float
    voltage_margin_v:float
    thermal_margin_c:float
    equivalent_cycles:float
    reserve_soc:float
    status:str


class BatteryTwin:
    """Educational 1-RC Thevenin pack model, not a characterized cell BMS."""
    def __init__(self,wh,series,soc=1.,soh=1.,temperature=25.,max_c=8.,
                 resistance_scale=1.,imbalance_mv=0.,degraded=False,reserve=.10,ideal=False):
        self.nominal_wh=max(1.,float(wh));self.series=max(1,int(series))
        self.nominal_voltage=3.7*self.series
        self.capacity_ah=self.nominal_wh/self.nominal_voltage
        self.soc=clamp01(soc);self.soh=clamp(soh,.5,1.)
        self.temp=float(temperature);self.max_c=max(.5,float(max_c))
        self.resistance_scale=max(.25,float(resistance_scale))
        self.imbalance=max(0.,float(imbalance_mv)/1000.)
        self.degraded=bool(degraded);self.reserve=clamp(reserve,0.,.5)
        self.ideal=bool(ideal)
        self.rc_v=0.;self.throughput_wh=0.
        self.base_r0=max(.003,min(.18,.018*(self.nominal_voltage/22.2)/
                                  max(.45,math.sqrt(self.capacity_ah/5.))))
        self.thermal_capacity=max(500.,10.*self.nominal_wh)
        self.thermal_resistance=max(.08,min(1.2,.80*(100/self.nominal_wh)**.3))
        self.ocv=self.open_circuit_voltage();self.terminal_v=self.ocv
        self.current=0.;self.demanded=0.;self.delivered=0.;self.limit=0.
        self.limited=False;self.heat=0.;self.status='NORMAL'
        self.min_cell_v=self.ocv/self.series
        self.max_cell_v=self.min_cell_v
        self.initial_usable_wh=self.remaining_wh()

    def temperature_factor(self):
        if self.ideal:return 1.
        points=[(-50,.50),(-10,.65),(0,.78),(10,.88),(20,.97),(30,1.),(40,.96),(80,.90)]
        return float(np.interp(self.temp,[x[0] for x in points],[x[1] for x in points]))

    def fault_factor(self):return .88 if self.degraded and not self.ideal else 1.
    def usable_wh(self):return self.nominal_wh*self.temperature_factor()*self.soh*self.fault_factor()
    def remaining_wh(self):return self.soc*self.usable_wh()

    def open_circuit_voltage(self):
        if self.ideal:return self.nominal_voltage
        socs=[0,.03,.08,.15,.30,.50,.70,.85,.95,1.]
        cells=[3.,3.2,3.4,3.52,3.66,3.76,3.86,3.98,4.12,4.2]
        return self.series*float(np.interp(self.soc,socs,cells))

    def resistance(self):
        if self.ideal:return 0.
        cold=min(2.8,1+.035*max(0.,25-self.temp))
        hot=1+.006*max(0.,self.temp-35)
        aging=1+1.8*(1-self.soh)
        low_soc=1+.8*max(0.,.15-self.soc)/.15
        return self.base_r0*self.resistance_scale*cold*hot*aging*low_soc*(1.65 if self.degraded else 1.)

    def max_current(self):
        tf=.55 if self.temp<0 else (.75 if self.temp<10 else (.65 if self.temp>55 else 1.))
        return self.capacity_ah*self.max_c*self.soh*tf*(.65 if self.degraded else 1.)

    def _max_power(self):
        if self.ideal:return float('inf')
        effective=max(0.,self.ocv-self.rc_v)
        vmin=self.series*(3.2+.5*self.imbalance)
        r0=max(1e-6,self.resistance())
        if effective<=vmin or self.soc<=0:return 0.
        current=min(self.max_current(),(effective-vmin)/r0,effective/(2*r0))
        return max(0.,current*(effective-current*r0))

    def step(self,demand_w,ambient,dt):
        dt=max(1e-4,float(dt));self.demanded=max(0.,float(demand_w))
        self.ocv=self.open_circuit_voltage()
        if self.ideal:
            self.limit=self.nominal_wh*self.soc*3600./dt
            self.delivered=min(self.demanded,self.limit)
            self.soc=max(0.,self.soc-self.delivered*dt/(3600.*self.nominal_wh))
            self.terminal_v=self.nominal_voltage
            self.current=self.delivered/max(.001,self.nominal_voltage)
            self.temp=float(ambient);self.heat=0.;self.rc_v=0.
            self.min_cell_v=self.max_cell_v=self.nominal_voltage/self.series
        else:
            self.limit=self._max_power()
            self.delivered=min(self.demanded,self.limit)
            r0=max(1e-6,self.resistance())
            veff=max(1e-3,self.ocv-self.rc_v)
            discriminant=max(0.,veff**2-4*r0*self.delivered)
            self.current=min(self.max_current(),
                (veff-math.sqrt(discriminant))/(2*r0)) if self.delivered>0 else 0.
            self.terminal_v=max(0.,veff-r0*self.current)
            # Coulomb counting uses charge capacity, not the temporary thermal
            # derating factor (which is an available-energy estimate).
            charge_ah=max(.05,self.capacity_ah*self.soh*self.fault_factor())
            self.soc=max(0.,self.soc-self.current*dt/(3600.*charge_ah))
            r1=max(1e-5,.6*r0)
            a=math.exp(-dt/18.)
            self.rc_v=clamp(a*self.rc_v+(1-a)*self.current*r1,0.,.25*self.ocv)
            self.heat=self.current**2*r0+self.current*self.rc_v
            self.temp+=(self.heat-(self.temp-float(ambient))/self.thermal_resistance)*dt/self.thermal_capacity
            stress=1+.18*max(0.,self.current/max(.05,self.capacity_ah)-1.)+.035*max(0.,self.temp-35.)
            self.soh=max(.5,self.soh-.00035*(self.delivered*dt/(3600*self.nominal_wh))*stress)
            mean=self.terminal_v/self.series
            self.min_cell_v=max(0.,mean-.5*self.imbalance)
            self.max_cell_v=mean+.5*self.imbalance
        self.throughput_wh+=self.delivered*dt/3600.
        self.limited=self.delivered+1e-5<self.demanded
        flags=[]
        if self.limited:flags.append('POWER_LIMITED')
        if not self.ideal and self.min_cell_v<=3.25:flags.append('LOW_VOLTAGE')
        if self.temp>=57 and not self.ideal:flags.append('THERMAL_LIMIT')
        if self.soc<=self.reserve:flags.append('RESERVE')
        if self.degraded and not self.ideal:flags.append('DEGRADED_CELL')
        self.status='+'.join(flags) if flags else ('IDEAL_RESERVOIR' if self.ideal else 'NORMAL')
        return self.snapshot()

    def snapshot(self):
        return BatterySnapshot(self.soc,self.soh,self.nominal_wh,self.nominal_wh*self.temperature_factor(),
            self.nominal_wh*self.temperature_factor()*self.soh,self.usable_wh(),self.remaining_wh(),
            self.ocv,self.terminal_v,self.current,self.current/max(.05,self.capacity_ah),self.resistance(),
            self.rc_v,self.demanded,self.delivered,self.limit,self.limited,self.temp,self.heat,
            self.min_cell_v,self.max_cell_v,self.min_cell_v-3.2,60-self.temp,
            self.throughput_wh/self.nominal_wh,self.reserve,self.status)

    def telemetry(self):
        return {'battery_'+k:v for k,v in asdict(self.snapshot()).items()}

# ============================================================================
# ACTUATION, POWER CONVERSION, FLIGHT PLANT
# ============================================================================
@dataclass
class Control:
    throttle:float=.5
    aileron:float=0.
    elevator:float=0.
    rudder:float=0.
    heading_deg:float=0.
    altitude_m:float=100.
    speed_ms:float=15.


@dataclass
class FlightState:
    time_s:float=0.
    north_m:float=0.
    east_m:float=0.
    down_m:float=-100.
    altitude_m:float=100.
    u_ms:float=0.
    v_ms:float=0.
    w_ms:float=0.
    vn_ms:float=0.
    ve_ms:float=0.
    vd_ms:float=0.
    qw:float=1.
    qx:float=0.
    qy:float=0.
    qz:float=0.
    roll_deg:float=0.
    pitch_deg:float=0.
    yaw_deg:float=0.
    p_rad_s:float=0.
    q_rad_s:float=0.
    r_rad_s:float=0.
    airspeed_ms:float=0.
    ground_speed_ms:float=0.
    vertical_speed_ms:float=0.
    alpha_deg:float=0.
    beta_deg:float=0.
    throttle_cmd:float=0.
    aileron_cmd:float=0.
    elevator_cmd:float=0.
    rudder_cmd:float=0.
    throttle_actual:float=0.
    aileron_actual:float=0.
    elevator_actual:float=0.
    rudder_actual:float=0.
    fx_body_n:float=0.
    fy_body_n:float=0.
    fz_body_n:float=0.
    roll_moment_nm:float=0.
    pitch_moment_nm:float=0.
    yaw_moment_nm:float=0.
    gust_n_ms:float=0.
    gust_e_ms:float=0.
    gust_d_ms:float=0.
    envelope_active:bool=False
    envelope_mode:str='NORMAL'
    stall_warning:bool=False
    alpha_margin_deg:float=999.
    battery_wh:float=0.
    battery_soc:float=1.
    battery_temp_c:float=25.
    battery_health:float=1.
    fuel_mass_kg:float=0.
    fuel_fraction:float=1.
    mass_kg:float=1.
    motor_temp_c:float=25.
    motor_health:float=1.
    shaft_power_w:float=0.
    engine_shaft_w:float=0.
    power_draw_w:float=0.
    demanded_power_w:float=0.
    thrust_n:float=0.
    power_limited:bool=False
    hotel_delivered_w:float=0.
    actuator_delivered_w:float=0.
    propulsive_electrical_w:float=0.
    active_waypoint:int=0
    wp_distance_m:float=0.
    flight_mode:str='WAYPOINT'
    def quaternion(self):return [self.qw,self.qx,self.qy,self.qz]


@dataclass
class ActuatorChannel:
    value:float=0.
    tau:float=.15
    rate:float=4.
    low:float=-1.
    high:float=1.
    def update(self,command,dt):
        slew=clamp((clamp(command,self.low,self.high)-self.value)/max(.001,self.tau),-self.rate,self.rate)
        self.value=clamp(self.value+slew*dt,self.low,self.high)
        return self.value


class Actuators:
    def __init__(self,kind,trim):
        self.channels={
            'throttle':ActuatorChannel(trim.throttle,.35 if kind=='fixed' else .18,1.2 if kind=='fixed' else 2.,0.,1.),
            'aileron':ActuatorChannel(0.,.10 if kind=='fixed' else .08,4.5 if kind=='fixed' else 6.),
            'elevator':ActuatorChannel(trim.elevator if kind=='fixed' else 0.,.12 if kind=='fixed' else .08,4.),
            'rudder':ActuatorChannel(0.,.15 if kind=='fixed' else .10,3. if kind=='fixed' else 5.),
        }
    def update(self,c,dt):
        vals={name:channel.update(getattr(c,name),dt) for name,channel in self.channels.items()}
        return Control(**vals,heading_deg=c.heading_deg,altitude_m=c.altitude_m,speed_ms=c.speed_ms)


@dataclass
class PropulsionResult:
    thrust_n:float=0.
    demanded_w:float=0.
    electrical_w:float=0.
    propulsion_electric_w:float=0.
    shaft_w:float=0.
    hotel_w:float=0.
    actuator_w:float=0.
    fuel_kg_s:float=0.
    limited:bool=False
    authority:float=1.
    engine_shaft_w:float=0.


class Propulsion:
    def __init__(self,profile,p,battery=None):
        self.profile=profile;self.p=p;self.battery=battery
        self.esc_eff=.96;self.motor_eff=.90;self.figure_merit=.72
        self.hotel=float(profile.get('hotel_W',15.))
        self.kind=profile['power_system']
        if self.kind=='Battery':
            reference=float(profile.get('draw_watt',180.))
            self.max_electrical=max(1.8*reference,1.5*reference) if p.kind=='rotor' else max(2.8*reference,250.)
            self.max_shaft=self.max_electrical*self.esc_eff*self.motor_eff
        else:
            self.max_electrical=0.
            self.max_shaft=float(profile.get('max_shaft_power_w',50000.))

    def _fixed_thrust(self,shaft,airspeed):
        efficiency=clamp(self.profile.get('prop_eff',.72),.3,.9)
        # Not a manufacturer propeller map; avoid P/V singularity.
        cap=.95*self.p.mass_reference*G
        return min(cap,efficiency*shaft/max(4.,airspeed))

    def _rotor_thrust(self,shaft,density,airspeed):
        rho=max(.2,density);area=max(.03,self.p.rotor_disk_area)
        # Fuselage drag is accounted for in the rigid-body force balance.
        # Do not deduct it again from shaft power (double counting).
        available=max(0.,shaft)
        thrust=(available*self.figure_merit*math.sqrt(2*rho*area))**(2/3) if available>0 else 0.
        return min(2.4*self.p.mass_reference*G,thrust)

    def step(self,act,airspeed,env,dt,fuel,motor_health):
        actuator_demand=(4. if self.p.kind=='fixed' else 8.)*(abs(act.aileron)+abs(act.elevator)+abs(act.rudder))
        health=clamp(motor_health,.35,1.)
        if self.kind=='Battery':
            prop_demand=act.throttle*self.max_electrical
            demand=self.hotel+actuator_demand+prop_demand
            delivered=self.battery.step(demand,env.temperature_c,dt).delivered_w if self.battery else demand
            # Priority ordering: essential hotel loads, then actuators, then
            # propulsion. A low-power pack cannot silently satisfy all loads.
            hotel_received=min(self.hotel,delivered)
            actuator_received=min(actuator_demand,max(0.,delivered-hotel_received))
            prop_received=max(0.,delivered-hotel_received-actuator_received)
            shaft=prop_received*self.esc_eff*self.motor_eff*health
            limited=delivered+1e-6<demand
            authority=clamp(shaft/max(1.,self.max_shaft),0.,1.)
            thrust=(self._fixed_thrust(shaft,airspeed) if self.p.kind=='fixed'
                    else self._rotor_thrust(shaft,env.density,airspeed))
            return PropulsionResult(thrust,demand,delivered,prop_received,shaft,
                                    hotel_received,actuator_received,0.,limited,authority)
        engine_shaft=act.throttle*self.max_shaft*health if fuel>0 else 0.
        # Electrical hotel + servo power on an ICE aircraft requires an
        # engine-driven alternator. Approximate alternator efficiency at 80%.
        aux_shaft=(self.hotel+actuator_demand)/.80 if fuel>0 else 0.
        propeller_shaft=max(0.,engine_shaft-aux_shaft)
        bsfc=max(100.,float(self.profile.get('bsfc_gpkwh',300.)))
        fuel_rate=bsfc*(engine_shaft/1000.)/1000./3600.
        thrust=self._fixed_thrust(propeller_shaft,airspeed)
        return PropulsionResult(thrust,0.,0.,0.,propeller_shaft,
                                self.hotel if fuel>0 else 0.,
                                actuator_demand if fuel>0 else 0.,
                                fuel_rate,fuel<=0.,propeller_shaft/max(1.,self.max_shaft),
                                engine_shaft_w=engine_shaft)


@dataclass
class PID:
    kp:float
    ki:float
    kd:float
    ilim:float=1.
    integral:float=0.
    previous:float=0.
    initialized:bool=False
    def step(self,error,dt):
        derivative=(error-self.previous)/max(.001,dt) if self.initialized else 0.
        self.initialized=True;self.previous=error
        self.integral=clamp(self.integral+error*dt,-self.ilim,self.ilim)
        return self.kp*error+self.ki*self.integral+self.kd*derivative


def heading_error(target,current):return (target-current+180)%360-180


def waypoint_command(state,waypoints,capture):
    ix=max(0,min(state.active_waypoint,len(waypoints)-1))
    n,e,h=waypoints[ix]
    dist=math.hypot(n-state.north_m,e-state.east_m)
    if dist<=capture and ix<len(waypoints)-1:
        ix+=1;n,e,h=waypoints[ix];dist=math.hypot(n-state.north_m,e-state.east_m)
    angle=math.degrees(math.atan2(e-state.east_m,n-state.north_m))%360.
    return ix,angle,dist,h,ix==len(waypoints)-1 and dist<=capture


class Autopilot:
    """Uses SIMULATED TRUTH STATE, not INS/EKF, by architecture design."""
    def __init__(self,p,trim):
        self.p=p;self.trim=trim
        if p.kind=='fixed':
            self.roll=PID(.035,.003,.008,6.);self.pitch=PID(.070,.005,.012,8.)
            self.speed=PID(.085,.015,.010,8.)
        else:
            self.roll=PID(.09,.008,.018,6.);self.pitch=PID(.09,.008,.018,6.)
            self.altitude=PID(.035,.008,.018,20.)
    def command(self,s,heading,altitude,speed,dt):
        herror=heading_error(heading,s.yaw_deg)
        if self.p.kind=='fixed':
            roll_target=clamp(.28*herror,-15.,15.)
            pitch_target=clamp(self.trim.alpha_deg+.045*(altitude-s.altitude_m)-
                .40*s.vertical_speed_ms+.015*abs(s.roll_deg),
                self.trim.alpha_deg-6.,self.trim.alpha_deg+8.)
            # Rate-damped attitude loops; actuators and aerodynamic moments
            # are already dynamic. Avoid differentiating noisy angle error.
            a=clamp(.017*(roll_target-s.roll_deg)-.42*s.p_rad_s,-.40,.40)
            e=clamp(self.trim.elevator-.018*(pitch_target-s.pitch_deg)+
                    .45*s.q_rad_s,-.40,.40)
            t=clamp(self.trim.throttle+.045*(speed-s.airspeed_ms)+
                    .002*self.speed.step(speed-s.airspeed_ms,dt),.05,1.)
            r=clamp(.010*s.beta_deg-.18*s.r_rad_s,-.20,.20)
        else:
            roll_target=clamp(.38*herror,-18.,18.)
            pitch_target=clamp(-1.10*(speed-s.ground_speed_ms),-15.,10.)
            a=clamp(.30*math.radians(roll_target-s.roll_deg)-
                    .75*s.p_rad_s,-.65,.65)
            e=clamp(.30*math.radians(pitch_target-s.pitch_deg)-
                    .75*s.q_rad_s,-.65,.65)
            t=clamp(self.trim.throttle+self.altitude.step((altitude-s.altitude_m)-
                1.20*s.vertical_speed_ms,dt),.10,1.)
            r=clamp(.24*math.radians(herror)-.65*s.r_rad_s,-.60,.60)
        return Control(t,a,e,r,heading,altitude,speed)


@dataclass
class EnvelopeStatus:
    active:bool=False
    mode:str='NORMAL'
    stall:bool=False
    overspeed:bool=False
    bank:bool=False
    alpha_margin_deg:float=999.


class EnvelopeProtection:
    def __init__(self,p,bank=35.,overspeed=32.):
        self.p=p;self.bank=bank;self.overspeed=overspeed
    def apply(self,s,c):
        if self.p.kind!='fixed':return c,EnvelopeStatus()
        alpha=abs(s.alpha_deg);stall=alpha>=.82*self.p.alpha_stall_deg
        deep=alpha>=self.p.alpha_stall_deg
        over=s.airspeed_ms>=self.overspeed
        bank=abs(s.roll_deg)>=self.bank
        t,a,e,r=c.throttle,c.aileron,c.elevator,c.rudder
        modes=[]
        if abs(s.p_rad_s)>.75:modes.append('ROLL_RATE');a=clamp(-.28*s.p_rad_s,-.45,.45)
        if abs(s.q_rad_s)>.65:modes.append('PITCH_RATE');e=clamp(.30*s.q_rad_s,-.45,.45)
        if abs(s.r_rad_s)>.75:modes.append('YAW_RATE');r=clamp(.22*s.r_rad_s,-.20,.20)
        if bank:modes.append('BANK_LIMIT');a=clamp(-.018*s.roll_deg-.22*s.p_rad_s,-.55,.55)
        if s.pitch_deg>24:modes.append('PITCH_HIGH');e=max(e,clamp(.025*(s.pitch_deg-10)+.12*s.q_rad_s,.10,.45))
        elif s.pitch_deg< -18:modes.append('PITCH_LOW');e=min(e,clamp(.025*(s.pitch_deg+6)+.12*s.q_rad_s,-.45,-.10))
        if over:modes.append('OVERSPEED');t=min(t,.12);e=min(e,-.08)
        if stall:
            modes.append('STALL_PREVENTION');t=max(t,.95)
            # Positive elevator generates nose-down moment with cm_de < 0.
            e=(max(e,.24 if deep else .12) if s.alpha_deg>=0
               else min(e,-.24 if deep else -.12))
            a=clamp(-.15*s.p_rad_s,-.25,.25)
            r=clamp(.12*s.r_rad_s,-.15,.15)
        if s.altitude_m<25 and s.vertical_speed_ms< -2 and not deep:
            modes.append('GROUND_PROX');t=max(t,.90)
            e=min(e,-.18);a=clamp(-.02*s.roll_deg,-.3,.3)
        return Control(clamp01(t),clamp(a,-.65,.65),clamp(e,-.65,.65),
            clamp(r,-.25,.25),c.heading_deg,c.altitude_m,c.speed_ms),EnvelopeStatus(
                bool(modes),'+'.join(dict.fromkeys(modes)) if modes else 'NORMAL',
                stall,over,bank,self.p.alpha_stall_deg-alpha)


@dataclass
class GustState:
    n:float=0.
    e:float=0.
    d:float=0.


class DrydenStyleTurbulence:
    """Correlated first-order gust proxy. NOT a full Dryden spectral filter."""
    SIGMAS={'None':(0.,0.,0.),'Light':(.8,.8,.45),'Moderate':(1.8,1.8,1.),
            'Severe':(3.2,3.2,1.8)}
    def __init__(self,intensity='Light',seed=1234):
        self.intensity=intensity;self.rng=np.random.default_rng(seed)
        self.state=GustState()
    def step(self,base,airspeed,dt):
        sigmas=self.SIGMAS[self.intensity]
        def advance(old,sigma,length):
            if sigma==0:return 0.
            factor=math.exp(-dt/max(.05,length/max(3.,airspeed)))
            return factor*old+sigma*math.sqrt(max(0.,1-factor*factor))*self.rng.normal()
        self.state.n=advance(self.state.n,sigmas[0],80.)
        self.state.e=advance(self.state.e,sigmas[1],80.)
        self.state.d=advance(self.state.d,sigmas[2],40.)
        return Environment(base.density,base.temperature_c,base.pressure_pa,
            base.wind_n+self.state.n,base.wind_e+self.state.e,base.wind_d+self.state.d)


def forces_moments(s,env,p,c,prop):
    rotation=body_to_ned(s.quaternion())
    wind_body=rotation.T@np.array([env.wind_n,env.wind_e,env.wind_d])
    u,v,w=np.array([s.u_ms,s.v_ms,s.w_ms])-wind_body
    airspeed=max(.1,float(math.sqrt(u*u+v*v+w*w)))
    alpha=math.atan2(w,max(.1,u))
    beta=math.asin(clamp(v/airspeed,-.99,.99))
    qbar=.5*env.density*airspeed**2
    if p.kind=='fixed':
        ph=s.p_rad_s*p.span/(2*airspeed)
        qh=s.q_rad_s*p.chord/(2*airspeed)
        rh=s.r_rad_s*p.span/(2*airspeed)
        cl,cd,cm=aero_coefficients(math.degrees(alpha),p)
        cl+=p.cl_q*qh+p.cl_de*c.elevator
        cd+=.012*c.elevator**2
        cy=p.cy_beta*beta+p.cy_da*c.aileron+p.cy_dr*c.rudder
        lift,drag,side=qbar*p.area*cl,qbar*p.area*cd,qbar*p.area*cy
        fx=-drag*math.cos(alpha)+lift*math.sin(alpha)+prop.thrust_n
        fy=side;fz=-drag*math.sin(alpha)-lift*math.cos(alpha)
        cmroll=p.cl_beta*beta+p.cl_p*ph+p.cl_r*rh+p.cl_da*c.aileron+p.cl_dr*c.rudder
        cmpitch=cm+p.cm_q*qh+p.cm_de*c.elevator
        cmyaw=p.cn_beta*beta+p.cn_p*ph+p.cn_r*rh+p.cn_da*c.aileron+p.cn_dr*c.rudder
        lm=qbar*p.area*p.span*cmroll
        mm=qbar*p.area*p.chord*cmpitch
        nm=qbar*p.area*p.span*cmyaw
    else:
        drag_coeff=.5*max(.2,env.density)*p.rotor_drag_area
        fx=-drag_coeff*u*abs(u)
        fy=-drag_coeff*v*abs(v)
        fz=-prop.thrust_n-drag_coeff*w*abs(w)
        lm=c.aileron*p.max_roll_moment*prop.authority-.16*s.p_rad_s
        mm=c.elevator*p.max_pitch_moment*prop.authority-.16*s.q_rad_s
        nm=c.rudder*p.max_yaw_moment*prop.authority-.12*s.r_rad_s
    return dict(fx=fx,fy=fy,fz=fz,lm=lm,mm=mm,nm=nm,rotation=rotation,
                airspeed=airspeed,alpha=alpha,beta=beta)


def dynamics_derivatives(s,env,p,c,prop):
    fm=forces_moments(s,env,p,c,prop)
    mass=max(.05,s.mass_kg)
    scale=mass/max(.05,p.mass_reference)
    ix,iy,iz=p.ix*scale,p.iy*scale,p.iz*scale
    gravity_body=fm['rotation'].T@np.array([0.,0.,G])
    u,v,w=s.u_ms,s.v_ms,s.w_ms
    pp,qq,rr=s.p_rad_s,s.q_rad_s,s.r_rad_s
    un=rr*v-qq*w+fm['fx']/mass+gravity_body[0]
    vn=pp*w-rr*u+fm['fy']/mass+gravity_body[1]
    wn=qq*u-pp*v+fm['fz']/mass+gravity_body[2]
    pd=(fm['lm']+(iy-iz)*qq*rr)/ix
    qd=(fm['mm']+(iz-ix)*pp*rr)/iy
    rd=(fm['nm']+(ix-iy)*pp*qq)/iz
    vel_ned=fm['rotation']@np.array([u,v,w])
    return fm,(un,vn,wn,pd,qd,rd),vel_ned


class DigitalTwinEngine:
    def __init__(self,p,profile,propulsion,initial_mass,altitude,speed,trim,fuel=0.):
        self.p=p;self.profile=profile;self.propulsion=propulsion
        self.actuators=Actuators(p.kind,trim)
        pitch=math.radians(trim.alpha_deg if p.kind=='fixed' else 0.)
        q=q_from_euler(0.,pitch,0.)
        soc=propulsion.battery.soc if propulsion.battery else 1.
        self.initial_fuel=max(0.,fuel)
        self.state=FlightState(down_m=-altitude,altitude_m=altitude,
            u_ms=speed*math.cos(pitch),w_ms=speed*math.sin(pitch),
            qw=q[0],qx=q[1],qy=q[2],qz=q[3],pitch_deg=math.degrees(pitch),
            airspeed_ms=speed,alpha_deg=math.degrees(pitch),
            battery_wh=propulsion.battery.remaining_wh() if propulsion.battery else 0.,
            battery_soc=soc, fuel_mass_kg=self.initial_fuel,mass_kg=initial_mass)

    def step(self,command,environment,dt):
        s=self.state
        act=self.actuators.update(command,dt)
        prop=self.propulsion.step(act,max(1.,s.airspeed_ms),environment,dt,s.fuel_mass_kg,s.motor_health)
        fm,delta,vel_ned=dynamics_derivatives(s,environment,self.p,act,prop)
        for field,change,low,high in zip(
            ('u_ms','v_ms','w_ms','p_rad_s','q_rad_s','r_rad_s'),delta,
            (-100.,-160.,-160.,-8.,-8.,-8.),(350.,160.,160.,8.,8.,8.)):
            setattr(s,field,clamp(getattr(s,field)+change*dt,low,high))
        q=q_integrate(s.quaternion(),s.p_rad_s,s.q_rad_s,s.r_rad_s,dt)
        s.qw,s.qx,s.qy,s.qz=map(float,q)
        roll,pitch,yaw=euler_from_q(q)
        s.roll_deg=math.degrees(roll);s.pitch_deg=math.degrees(pitch);s.yaw_deg=math.degrees(yaw)%360
        s.north_m+=vel_ned[0]*dt;s.east_m+=vel_ned[1]*dt;s.down_m+=vel_ned[2]*dt
        if s.down_m>0:s.down_m=0.;s.w_ms=min(0.,s.w_ms)
        s.altitude_m=-s.down_m
        s.vn_ms,s.ve_ms,s.vd_ms=map(float,vel_ned)
        s.ground_speed_ms=math.hypot(s.vn_ms,s.ve_ms)
        s.vertical_speed_ms=-s.vd_ms
        s.airspeed_ms=fm['airspeed'];s.alpha_deg=math.degrees(fm['alpha'])
        s.beta_deg=math.degrees(fm['beta'])
        s.fx_body_n=fm['fx'];s.fy_body_n=fm['fy'];s.fz_body_n=fm['fz']
        s.roll_moment_nm=fm['lm'];s.pitch_moment_nm=fm['mm'];s.yaw_moment_nm=fm['nm']
        s.throttle_cmd=command.throttle;s.aileron_cmd=command.aileron
        s.elevator_cmd=command.elevator;s.rudder_cmd=command.rudder
        s.throttle_actual=act.throttle;s.aileron_actual=act.aileron
        s.elevator_actual=act.elevator;s.rudder_actual=act.rudder
        s.shaft_power_w=prop.shaft_w;s.engine_shaft_w=prop.engine_shaft_w
        s.thrust_n=prop.thrust_n
        s.power_draw_w=(prop.electrical_w if self.propulsion.kind=='Battery'
                        else prop.engine_shaft_w)
        s.demanded_power_w=prop.demanded_w;s.power_limited=prop.limited
        s.hotel_delivered_w=prop.hotel_w;s.actuator_delivered_w=prop.actuator_w
        s.propulsive_electrical_w=prop.propulsion_electric_w
        if self.propulsion.battery:
            b=self.propulsion.battery
            s.battery_wh=b.remaining_wh();s.battery_soc=b.soc
            s.battery_health=b.soh;s.battery_temp_c=b.temp
        if self.propulsion.kind=='ICE':
            burned=min(s.fuel_mass_kg,prop.fuel_kg_s*dt)
            s.fuel_mass_kg-=burned
            s.mass_kg=max(.1,s.mass_kg-burned)
            s.fuel_fraction=s.fuel_mass_kg/max(1e-9,self.initial_fuel)
            s.battery_soc=s.fuel_fraction
        if self.propulsion.kind=='Battery':
            target_heat=.08*prop.shaft_w
            thermal_cap=max(150.,120*self.p.mass_reference)
            cooling=(s.motor_temp_c-environment.temperature_c)/.35
            s.motor_temp_c+=(target_heat-cooling)*dt/thermal_cap
        else:
            target=environment.temperature_c+55+120*clamp01(prop.shaft_w/max(1.,self.propulsion.max_shaft))
            s.motor_temp_c+=(target-s.motor_temp_c)*(1-math.exp(-dt/45.))
        s.time_s+=dt
        return s

# ============================================================================
# SENSOR EMULATION AND SEPARATE INS / NAVIGATION EKF
# ============================================================================
@dataclass
class FaultConfig:
    gps_dropout:bool=True
    gps_start:float=90.
    gps_duration:float=45.
    imu_bias:bool=True
    baro_bias:bool=True
    motor_degradation:bool=False
    motor_start:float=150.
    degraded_health:float=.75
    def gps_available(self,t):
        return not (self.gps_dropout and self.gps_start<=t<self.gps_start+self.gps_duration)
    def motor_health(self,t):
        return clamp(self.degraded_health,.35,1.) if self.motor_degradation and t>=self.motor_start else 1.


@dataclass
class SensorPacket:
    time_s:float
    imu_new:bool=False
    gps_new:bool=False
    baro_new:bool=False
    airspeed_new:bool=False
    gps_valid:bool=False
    gps_north_m:Optional[float]=None
    gps_east_m:Optional[float]=None
    gps_altitude_m:Optional[float]=None
    gps_vn_ms:Optional[float]=None
    gps_ve_ms:Optional[float]=None
    baro_altitude_m:float=0.
    indicated_airspeed_ms:float=0.
    imu_fx_ms2:float=0.
    imu_fy_ms2:float=0.
    imu_fz_ms2:float=0.
    gyro_p_rad_s:float=0.
    gyro_q_rad_s:float=0.
    gyro_r_rad_s:float=0.


class SensorSuite:
    RATES={'imu':50.,'gps':5.,'baro':20.,'airspeed':20.}
    def __init__(self,seed=42):
        self.rng=np.random.default_rng(seed)
        self.next_t={name:0. for name in self.RATES}
        self.cache={'gps':(None,None,None,None,None,False),
                    'imu':(0.,0.,0.,0.,0.,0.),'baro':0.,'airspeed':0.}
    def due(self,name,t):
        if t+1e-9<self.next_t[name]:return False
        while self.next_t[name]<=t+1e-9:self.next_t[name]+=1./self.RATES[name]
        return True
    def measure(self,s,faults):
        t=s.time_s
        i,g,b,a=(self.due(name,t) for name in ('imu','gps','baro','airspeed'))
        if i:
            accel=np.array([s.fx_body_n,s.fy_body_n,s.fz_body_n])/max(.05,s.mass_kg)
            ab=.03 if faults.imu_bias else 0.
            gb=.002 if faults.imu_bias else 0.
            self.cache['imu']=tuple(float(x) for x in [
                accel[0]+ab+self.rng.normal(0,.08),
                accel[1]+ab+self.rng.normal(0,.08),
                accel[2]+ab+self.rng.normal(0,.08),
                s.p_rad_s+gb+self.rng.normal(0,.004),
                s.q_rad_s+gb+self.rng.normal(0,.004),
                s.r_rad_s+gb+self.rng.normal(0,.004)])
        if b:self.cache['baro']=s.altitude_m+(5. if faults.baro_bias else 0.)+self.rng.normal(0,1.2)
        if a:self.cache['airspeed']=max(0.,s.airspeed_ms+self.rng.normal(0,.35))
        if g:
            if faults.gps_available(t):
                self.cache['gps']=(s.north_m+self.rng.normal(0,2.5),
                    s.east_m+self.rng.normal(0,2.5),s.altitude_m+self.rng.normal(0,4.),
                    s.vn_ms+self.rng.normal(0,.25),s.ve_ms+self.rng.normal(0,.25),True)
            else:self.cache['gps']=(None,None,None,None,None,False)
        return SensorPacket(t,i,g,b,a,self.cache['gps'][5],*self.cache['gps'][:5],
                            float(self.cache['baro']),float(self.cache['airspeed']),
                            *self.cache['imu'])


class StrapdownINS:
    def __init__(self,q):self.q=qnormalize(q)
    def integrate(self,packet,dt):
        # Zero-order held gyro measurement integrates at EVERY internal step.
        # Avoids lost time if the simulation dt and IMU period differ.
        self.q=q_integrate(self.q,packet.gyro_p_rad_s,
            packet.gyro_q_rad_s,packet.gyro_r_rad_s,dt)
        body_specific=np.array([packet.imu_fx_ms2,packet.imu_fy_ms2,packet.imu_fz_ms2])
        return body_to_ned(self.q)@body_specific+np.array([0.,0.,G])


class BiasAwareEKF:
    """9-state N/E/h, Vn/Ve/Vh, horizontal acceleration biases, baro bias."""
    def __init__(self,altitude=100.,speed_n=0.):
        self.x=np.zeros((9,1));self.x[2,0]=altitude;self.x[3,0]=speed_n
        self.P=np.diag([25.,25.,16.,4.,4.,2.,.05**2,.05**2,9.])
    def predict(self,dt,acc_n,acc_e,acc_up):
        x=self.x
        ax=acc_n-x[6,0];ay=acc_e-x[7,0]
        x[0,0]+=x[3,0]*dt+.5*ax*dt*dt
        x[1,0]+=x[4,0]*dt+.5*ay*dt*dt
        x[2,0]+=x[5,0]*dt+.5*acc_up*dt*dt
        x[3,0]+=ax*dt;x[4,0]+=ay*dt;x[5,0]+=acc_up*dt
        F=np.eye(9)
        for pos,vel in [(0,3),(1,4),(2,5)]:F[pos,vel]=dt
        F[0,6]=F[1,7]=-.5*dt*dt
        F[3,6]=F[4,7]=-dt
        Q=np.diag([.06*dt,.06*dt,.06*dt,.22*dt,.22*dt,.18*dt,
                   2e-5*dt,2e-5*dt,4e-4*dt])
        self.P=F@self.P@F.T+Q
    def update(self,z,H,R):
        z=np.asarray(z,float).reshape(-1,1)
        H=np.asarray(H,float);R=np.asarray(R,float)
        innovation=z-H@self.x
        S=H@self.P@H.T+R
        # Cholesky not essential at this small dimension, solve avoids explicit inv.
        K=np.linalg.solve(S,(self.P@H.T).T).T
        self.x+=K@innovation
        I=np.eye(9);A=I-K@H
        self.P=A@self.P@A.T+K@R@K.T
        self.P=.5*(self.P+self.P.T)
    def update_gps(self,packet):
        H=np.zeros((5,9))
        for i in range(5):H[i,i]=1.
        self.update([packet.gps_north_m,packet.gps_east_m,packet.gps_altitude_m,
            packet.gps_vn_ms,packet.gps_ve_ms],H,
            np.diag([2.5**2,2.5**2,4.**2,.25**2,.25**2]))
    def update_baro(self,altitude):
        H=np.zeros((1,9));H[0,2]=1;H[0,8]=1
        self.update([altitude],H,np.array([[1.2**2]]))
    def telemetry(self):
        x=self.x[:,0];variances=np.maximum(0.,np.diag(self.P))
        return dict(est_north_m=float(x[0]),est_east_m=float(x[1]),
            est_altitude_m=float(x[2]),est_vn_ms=float(x[3]),
            est_ve_ms=float(x[4]),est_vertical_speed_ms=float(x[5]),
            est_accel_bias_n_ms2=float(x[6]),est_accel_bias_e_ms2=float(x[7]),
            est_baro_bias_m=float(x[8]),sigma_north_m=math.sqrt(variances[0]),
            sigma_east_m=math.sqrt(variances[1]),sigma_altitude_m=math.sqrt(variances[2]))


# ============================================================================
# SECONDARY LOW-ORDER HEURISTICS (NOT CERTIFIED DETECTION/NETWORK MODELS)
# ============================================================================
def compute_observability(delta_temp,alt,speed_kmh,clouds,gust_level,stealth_factor,
                          kind,power,visual_size,background,humidity):
    size=clamp01(visual_size/3.)
    altterm=1-min(.8,alt/1200.)
    speedterm=clamp01(speed_kmh/90.)
    motion=.18 if kind=='rotor' else .08
    reduction=1-max(0.,(stealth_factor-1.)*.18)
    visual=100*clamp01((.36*size+.30*altterm+.16*speedterm+.10*motion)*
             (1-.35*clamp01(background))*(1-.18*clouds/100.)*
             (1-.10*clamp01(humidity))*reduction)
    infrared=100*clamp01((.56*clamp01(delta_temp/25)+.18*clamp01(visual_size/2.5)+
             (.12 if power=='ICE' else .03)+.06*clamp01(speed_kmh/120.))*
             (1-min(.5,alt/2000.))*max(.45,(1-.22*clouds/100.)*
             (1-.18*clamp01(humidity)))*(1-.04*gust_level/10.)*reduction)
    confidence=clamp(1-(.20*clouds/100.+.18*background+.10*gust_level/10.),.45,.95)
    blend=(.4*visual+.6*infrared if power=='ICE' else
           (.55*visual+.45*infrared if kind=='rotor' else .5*(visual+infrared)))
    return {'visual_score':round(visual,1),'thermal_score':round(infrared,1),
            'overall_score':round(blend,1),'confidence':round(100*confidence,1)}


ROLES=['LEAD','SCOUT','RELAY','OBSERVER','TRACKER']


def simulate_swarm(config,waypoints,final,observability):
    """Separate low-order mission layer, not multiple 6-DOF twins."""
    rng=np.random.default_rng(config['swarm_seed'])
    count=config['swarm_size'];rounds=config['swarm_rounds']
    formation=config['swarm_spacing_m'];lead_energy=final.battery_soc*100.
    vehicles=[];history=[];log=[]
    for i in range(count):
        theta=2*math.pi*i/max(1,count)
        radius=formation*(.8+.35*rng.random()) if i else 0.
        vehicles.append(dict(vehicle_id=f'UAV-{i+1:02d}',role=ROLES[i%len(ROLES)],
            north_m=float(final.north_m+radius*math.cos(theta)),
            east_m=float(final.east_m+radius*math.sin(theta)),
            altitude_m=float(max(5.,final.altitude_m+rng.normal(0,5))),
            speed_kmh=float(max(5.,final.airspeed_ms*3.6*(.92+.16*rng.random()))),
            energy_pct=clamp(lead_energy-2*i/max(1,count-1),0,100),
            health_pct=clamp(100-abs(rng.normal(0,1.5)),75,100),
            observability_score=clamp(observability+rng.normal(0,2),0,100),
            current_waypoint=i%len(waypoints),action='STANDBY',status_note='Nominal'))
    for rnd in range(rounds):
        for v in vehicles:
            tn,te,ta=waypoints[v['current_waypoint']]
            threat_distance=math.hypot(v['north_m']-config['threat_n'],v['east_m']-config['threat_e'])
            in_zone=(config['threat_radius_km']>0 and
                     threat_distance<=1000*config['threat_radius_km'])
            if v['energy_pct']<=config['swarm_reserve']:
                action,reason='RTB','Energy reserve reached';tn,te=0.,0.
            elif in_zone:
                action,reason=('RELAY_COMMS','Maintain relay geometry') if v['role']=='RELAY' else ('RELOCATE','Limit zone dwell')
            elif config['swarm_coordination']:
                action,reason={'RELAY':('RELAY_COMMS','Communications relay'),
                    'TRACKER':('HANDOFF_TRACK','Maintain track continuity'),
                    'SCOUT':('RELOCATE','Advance survey position'),
                    'OBSERVER':('LOITER','Hold observation position')}.get(
                        v['role'],('SPEED_CHANGE','Coordinate formation speed'))
            else:action,reason='LOITER','Independent mission hold'
            speedscale={'RTB':.9,'LOITER':.55,'RELOCATE':1.05,
                        'SPEED_CHANGE':.88,'RELAY_COMMS':.60,'HANDOFF_TRACK':.82}.get(action,1.)
            if action=='RELAY_COMMS':ta=max(ta,final.altitude_m+40.)
            dist=math.hypot(tn-v['north_m'],te-v['east_m'])
            travel=min(dist,v['speed_kmh']*speedscale/3.6*45.*(.2 if action=='LOITER' else 1.))
            if dist>1e-6:
                v['north_m']+=travel*(tn-v['north_m'])/dist
                v['east_m']+=travel*(te-v['east_m'])/dist
            v['altitude_m']+=clamp(ta-v['altitude_m'],-20.,20.)
            if dist<=max(25.,travel+10.) and action!='RTB':
                v['current_waypoint']=(v['current_waypoint']+1)%len(waypoints)
            burn=(.45*(.55+v['speed_kmh']/max(25.,final.airspeed_ms*3.6))*
                  (1+.7*max(0.,config['stealth_drag']-1.)))
            burn*= {'LEAD':1.,'SCOUT':1.08,'RELAY':.9,'OBSERVER':.82,'TRACKER':.96}[v['role']]
            if action=='RTB':burn*=.88
            if action=='LOITER':burn*=.72
            v['energy_pct']=max(0.,v['energy_pct']-burn)
            v['action']=action;v['status_note']=reason
            v['observability_score']=clamp(observability-min(12.,v['altitude_m']/150.)-
                22*max(0.,config['stealth_drag']-1.)/.5+(8 if in_zone else 0)+
                rng.normal(0,1),0.,100.)
            history.append(dict(round=rnd+1,inside_threat_zone=in_zone,**v))
            log.append(dict(round=rnd+1,vehicle_id=v['vehicle_id'],action=action,reason=reason))
    df=pd.DataFrame(vehicles);energy=float(df.energy_pct.mean());health=float(df.health_pct.mean())
    observability=float(df.observability_score.mean())
    resilience=clamp(.40*health+35*clamp01((energy-config['swarm_reserve'])/
        max(1.,100.-config['swarm_reserve']))+5*min(5,len(set(df.role))),0,100)
    score=clamp(.38*energy+.32*resilience+.30*(100-observability),0,100)
    summary=dict(swarm_size=count,rounds=rounds,mean_energy_pct=energy,
        mean_health_pct=health,mean_observability_score=observability,
        resilience_score=resilience,swarm_score=score,
        rtb_count=int((df.action=='RTB').sum()))
    return dict(final=df,history=pd.DataFrame(history),coordination_log=log,summary=summary)


# ============================================================================
# SIMULATION ORCHESTRATION / INVARIANTS / ARTIFACTS
# ============================================================================
def parse_waypoints(text,default_alt):
    points=[]
    for item in text.split(';'):
        if not item.strip():continue
        numbers=[float(v.strip()) for v in item.split(',')]
        if len(numbers)==2:n,e=numbers;h=default_alt
        elif len(numbers)==3:n,e,h=numbers
        else:raise ValueError('Waypoints require north,east[,altitude], separated by semicolons.')
        if not all(math.isfinite(x) for x in (n,e,h)) or h<0:
            raise ValueError('Waypoints must have finite coordinates and non-negative altitudes.')
        points.append((n,e,h))
    if not points:raise ValueError('Specify at least one waypoint.')
    return points


def scenario_setup(config):
    name=config['aircraft']
    profile=dict(UAV_PROFILES[name])
    stealth=float(config['stealth_drag'])
    if profile['type']=='fixed':profile['cd0']*=stealth
    else:profile['parasitic_area_m2']*=stealth
    payload=config['payload_g']/1000.
    if profile['power_system']=='Battery':
        reference_battery=battery_mass_kg(profile['battery_wh'],220.)
        selected_battery=battery_mass_kg(config['battery_wh'],config['specific_energy'])
        mass=max(.1,profile['base_weight_kg']+payload+selected_battery-reference_battery)
        fuel=0.
    else:
        selected_battery=0.
        fuel=profile['fuel_tank_l']*config['fuel_fill']/100.*profile['fuel_density_kgpl']
        mass=max(.1,profile['base_weight_kg']+payload+fuel)
    atmosphere=atmosphere_state(config['altitude_m'],config['temp_c'])
    params=build_dynamics_params(profile,mass)
    battery=None
    if profile['power_system']=='Battery':
        battery=BatteryTwin(config['battery_wh'],config['series_cells'],
            config['battery_soc']/100.,config['battery_soh']/100.,
            config['battery_temp'],config['max_c_rate'],config['resistance_scale'],
            config['cell_imbalance_mv'],config['degraded_cell'],
            config['reserve_soc']/100.,ideal=not config['battery_twin'])
    prop=Propulsion(profile,params,battery)
    speed=config['speed_kmh']/3.6
    trim=solve_trim(params,profile,atmosphere[0],speed,mass,prop.max_shaft)
    return profile,mass,selected_battery,fuel,params,battery,prop,trim


def run_physics(config):
    waypoints=parse_waypoints(config['waypoints'],config['altitude_m'])
    profile,mass,batt_mass,fuel,params,battery,prop,trim=scenario_setup(config)
    speed=config['speed_kmh']/3.6
    # Multicopter initializes at rest. Fixed wing initializes near trim.
    engine=DigitalTwinEngine(params,profile,prop,mass,config['altitude_m'],
                             speed if params.kind=='fixed' else 0.,trim,fuel)
    autopilot=Autopilot(params,trim)
    envelope=EnvelopeProtection(params,config['max_bank'],config['overspeed'])
    wind_to=math.radians((config['wind_from']+180)%360.)
    steady_n=config['wind_kmh']/3.6*math.cos(wind_to)
    steady_e=config['wind_kmh']/3.6*math.sin(wind_to)
    turbulence=DrydenStyleTurbulence(config['turbulence'],config['turb_seed'])
    sensors=SensorSuite(config['sensor_seed'])
    ekf=BiasAwareEKF(config['altitude_m'],speed if params.kind=='fixed' else 0.)
    ins=StrapdownINS(engine.state.quaternion())
    faults=FaultConfig(config['gps_dropout'],config['gps_start'],config['gps_duration'],
                       config['imu_bias'],config['baro_bias'],config['motor_fault'],
                       config['motor_start'],config['motor_health'])
    # 50-Hz IMU and 20-Hz barometer: substeps <= 0.02 s.
    output_dt=float(config['dt'])
    substeps=math.ceil(output_dt/.02)
    dt=output_dt/substeps
    total_steps=int(config['duration_min']*60/output_dt)
    rows=[];status='DURATION_LIMIT';last_packet=None
    previous_position=None
    for _ in range(total_steps):
        s=engine.state;s.motor_health=faults.motor_health(s.time_s)
        ix,heading,dist,command_alt,complete=waypoint_command(s,waypoints,config['capture_radius'])
        s.active_waypoint=ix;s.wp_distance_m=dist
        raw=autopilot.command(s,heading,command_alt,speed,output_dt)
        protected,envelope_status=(envelope.apply(s,raw) if config['envelope'] else
            (raw,EnvelopeStatus(alpha_margin_deg=params.alpha_stall_deg-abs(s.alpha_deg)
                                if params.kind=='fixed' else 999.)))
        for _inner in range(substeps):
            rho,t,p=atmosphere_state(s.altitude_m,config['temp_c'])
            ambient=Environment(rho,t,p,steady_n,steady_e,0.)
            env=turbulence.step(ambient,max(3.,s.airspeed_ms),dt)
            s=engine.step(protected,env,dt)
            s.gust_n_ms=env.wind_n-steady_n;s.gust_e_ms=env.wind_e-steady_e
            s.gust_d_ms=env.wind_d
            s.envelope_active=envelope_status.active
            s.envelope_mode=envelope_status.mode
            s.stall_warning=envelope_status.stall
            s.alpha_margin_deg=envelope_status.alpha_margin_deg
            last_packet=sensors.measure(s,faults)
            # IMU sample is held until the next sample, but propagated on every
            # integration substep. GPS/barometer updates remain event-driven.
            acceleration=ins.integrate(last_packet,dt)
            ekf.predict(dt,acceleration[0],acceleration[1],-acceleration[2])
            if last_packet.gps_new and last_packet.gps_valid:ekf.update_gps(last_packet)
            if last_packet.baro_new:ekf.update_baro(last_packet.baro_altitude_m)
            if s.altitude_m<=.05 and s.time_s>2.:
                status='GROUND_CONTACT';break
        row=asdict(s)
        row.update(asdict(last_packet))
        row.update(ekf.telemetry())
        if battery:row.update(battery.telemetry())
        row.update(dict(command_heading_deg=heading,command_altitude_m=command_alt,
            command_speed_ms=speed,raw_throttle_cmd=raw.throttle,
            raw_aileron_cmd=raw.aileron,raw_elevator_cmd=raw.elevator,
            raw_rudder_cmd=raw.rudder,rho_kgm3=rho,ambient_temperature_c=t,
            pressure_pa=p))
        row['horizontal_error_m']=math.hypot(row['est_north_m']-row['north_m'],
                                               row['est_east_m']-row['east_m'])
        row['vertical_error_m']=row['est_altitude_m']-row['altitude_m']
        row['position_error_m']=math.hypot(row['horizontal_error_m'],row['vertical_error_m'])
        row['quaternion_norm']=math.sqrt(sum(getattr(s,k)**2 for k in ('qw','qx','qy','qz')))
        row['power_accounting_residual_w']=(row['power_draw_w']-row['hotel_delivered_w']-
            row['actuator_delivered_w']-row['propulsive_electrical_w']) if battery else 0.
        rows.append(row)
        if not all(math.isfinite(row[key]) for key in ('north_m','east_m','altitude_m',
                            'u_ms','v_ms','w_ms','qw','qx','qy','qz')):
            status='DYNAMICS_NONFINITE';break
        if status=='GROUND_CONTACT':break
        if battery and s.battery_soc<=.001:status='ENERGY_EXHAUSTED';break
        if profile['power_system']=='ICE' and s.fuel_fraction<=.001:
            status='ENERGY_EXHAUSTED';break
        if complete:status='WAYPOINTS_COMPLETE';break
        previous_position=(s.north_m,s.east_m)
    telemetry=pd.DataFrame(rows)
    if telemetry.empty:raise RuntimeError('No telemetry was generated.')
    final=telemetry.iloc[-1]
    gust=np.sqrt(telemetry.gust_n_ms**2+telemetry.gust_e_ms**2+telemetry.gust_d_ms**2)
    metrics=dict(status=status,sim_time_s=float(final.time_s),initial_mass_kg=mass,
        final_mass_kg=float(final.mass_kg),gps_availability_pct=float(100*telemetry.gps_valid.mean()),
        rms_nav_error_m=math.sqrt(float(np.mean(telemetry.position_error_m**2))),
        max_nav_error_m=float(telemetry.position_error_m.max()),
        envelope_intervention_pct=float(100*telemetry.envelope_active.mean()),
        max_abs_alpha_deg=float(telemetry.alpha_deg.abs().max()),
        max_gust_ms=float(gust.max()),
        max_quaternion_norm_error=float(np.max(np.abs(telemetry.quaternion_norm-1.))),
        max_power_residual_w=float(np.max(np.abs(telemetry.power_accounting_residual_w))),
        trim_converged=bool(trim.converged),trim_power_feasible=bool(trim.power_feasible),
        max_position_sigma_m=float(telemetry.sigma_north_m.max()),
        final_soc_pct=float(final.battery_soc*100),
        depleted=(status=='ENERGY_EXHAUSTED'))
    temperature_contrast=max(0.,float(final.motor_temp_c-final.ambient_temperature_c),
                             float(final.battery_temp_c-final.ambient_temperature_c))
    observability=compute_observability(temperature_contrast,float(final.altitude_m),
        float(final.airspeed_ms*3.6),config['cloud_cover'],
        {'None':0,'Light':2,'Moderate':5,'Severe':8}[config['turbulence']],
        config['stealth_drag'],profile['type'],profile['power_system'],
        config['effective_size'],config['background'],config['humidity'])
    swarm=simulate_swarm(config,waypoints,final,observability['overall_score']) if config['swarm_enabled'] else None
    config_export={k:(int(v) if isinstance(v,np.integer) else v) for k,v in config.items()}
    scenario=dict(version=VERSION,aircraft=config['aircraft'],profile=profile,
        config=config_export,initial_mass_kg=mass,trim=asdict(trim),metrics=metrics,
        observability=observability,waypoints=waypoints,
        architecture=dict(guidance_feedback='simulated truth state',
                          ekf_role='navigation estimation and reporting only',
                          sensor_model='held 50-Hz body-frame IMU, 5-Hz GNSS, 20-Hz baro and airspeed',
                          turbulence='first-order correlated Dryden-style gust proxy',
                          flight_interface='not implemented',gpt_guidance='not implemented'))
    if battery:
        scenario['battery_model']=dict(name='idealized reservoir' if battery.ideal else '1-RC Thevenin proxy',
            mass_kg=batt_mass,initial_usable_wh=battery.initial_usable_wh,
            delivered_electrical_energy_wh=battery.throughput_wh,
            estimated_usable_energy_change_wh=battery.initial_usable_wh-battery.remaining_wh(),
            final_state=battery.telemetry())
    else:
        scenario['fuel_model']=dict(initial_fuel_kg=fuel,
            remaining_fuel_kg=float(final.fuel_mass_kg),
            bsfc_gpkwh=float(profile['bsfc_gpkwh']))
    if swarm:scenario['swarm']=dict(summary=swarm['summary'],
        vehicles=swarm['final'].to_dict('records'),coordination_log=swarm['coordination_log'])
    return dict(telemetry=telemetry,final=final,metrics=metrics,
        trim=trim,params=params,profile=profile,observability=observability,
        waypoints=waypoints,swarm=swarm,scenario=scenario)

# ============================================================================
# INTERACTIVE 3D BATTERY PACK REPLAY
# ============================================================================
# This is a visualization of the existing pack-level battery digital twin.
# Series-group voltages interpolate between the model's pack-level min/max
# estimates while preserving the model's terminal pack voltage. Parallel
# cells share series-group voltage. Temperature gradients are illustrative,
# not independently solved cell thermal states. The geometry/topology is not
# an assertion about the manufacturer's actual battery-pack construction.

BATTERY_3D_SCALES = {
    'Cell voltage (V)': (3.0, 4.2, [
        [0, '#ad233c'], [.16, '#fb8549'], [.33, '#ffe07a'],
        [.58, '#3bc6d2'], [1, '#20f59e']]),
    'Temperature proxy (°C)': (-20., 70., [
        [0, '#2855cf'], [.29, '#49bfff'], [.52, '#27d6ad'],
        [.70, '#ffd76a'], [1, '#ef4a5e']]),
    'Pack SOC (%)': (0., 100., [
        [0, '#a62648'], [.30, '#f3ae4c'], [.65, '#47bbae'], [1, '#21f59c']]),
    'Cell voltage margin (V)': (-.2, 1., [
        [0, '#a62648'], [.17, '#f16852'], [.4, '#e9cd5d'],
        [.7, '#27c9b8'], [1, '#19f196']]),
}


def inferred_parallel_count(wh, series_cells, assumed_cell_ah=5.):
    """Display-only topology estimate based on an explicitly assumed cell Ah."""
    denom=max(1.,int(series_cells))*3.7*max(.1,float(assumed_cell_ah))
    return int(clamp(round(float(wh)/denom),1,6))


def representative_battery_cells(frame, series_cells, parallel_cells,
                                 thermal_spread_c=0., nominal_wh=None):
    """Derive a pack-voltage-consistent *visual* cell array from telemetry.

    This is not a multi-cell electrochemical solver or a thermal FEM model.
    It yields one terminal voltage per series-connected parallel group.
    """
    series=int(clamp(series_cells,1,48))
    parallel=int(clamp(parallel_cells,1,8))
    vpack=float(frame['battery_terminal_v'])
    vmean=vpack/series
    vlo=float(frame['battery_min_cell_v'])
    vhi=float(frame['battery_max_cell_v'])
    # The pack model provides symmetric end points around the mean except
    # for floating-point differences. Rescale to enforce pack-voltage closure.
    spread=max(0.,(vhi-vlo)*.5)
    voltage_levels=vmean+np.linspace(-spread,spread,series)
    # Constrain any endpoint roundoff while keeping the string sum exact.
    voltage_levels+= (vpack-float(voltage_levels.sum()))/series
    assert abs(float(voltage_levels.sum())-vpack)<1e-7
    group_columns=int(math.ceil(math.sqrt(series)))
    pp_cols=int(math.ceil(math.sqrt(parallel)))
    pp_rows=int(math.ceil(parallel/pp_cols))
    group_rows=int(math.ceil(series/group_columns))
    cell_soc=float(frame['battery_soc'])*100.
    pack_temp=float(frame['battery_temperature_c'])
    wh=float(nominal_wh if nominal_wh is not None else frame['battery_nominal_wh'])
    implied_cell_ah=wh/max(1e-6,3.7*series*parallel)
    rows=[]
    for group in range(series):
        gx,gy=group%group_columns,group//group_columns
        # Zero-mean, user-controlled visual offset; not derived from the
        # pack's thermal ODE or from measured individual cell temperatures.
        thermal_offset=(group-(series-1)/2.)/max(1.,series-1)*float(thermal_spread_c)
        for index in range(parallel):
            px,py=index%pp_cols,index//pp_cols
            x=gx*(pp_cols*1.43+1.3)+px*1.43
            y=gy*(pp_rows*1.43+1.3)+py*1.43
            rows.append(dict(
                cell_id=f'S{group+1:02d}-P{index+1:02d}',
                series_group=group+1,parallel_cell=index+1,
                x=float(x),y=float(y),z=0.72,
                voltage_v=float(voltage_levels[group]),
                voltage_margin_v=float(voltage_levels[group]-3.2),
                temperature_proxy_c=float(pack_temp+thermal_offset),
                soc_pct=cell_soc,
                soh_pct=float(frame['battery_soh'])*100.,
                implied_cell_capacity_ah=implied_cell_ah,
                pack_time_s=float(frame['time_s']),
            ))
    return pd.DataFrame(rows)


def battery_cylinder_mesh(cx,cy,r=.53,height=1.44,segments=12):
    theta=np.linspace(0.,2.*math.pi,int(segments),endpoint=False)
    ring_x=cx+r*np.cos(theta);ring_y=cy+r*np.sin(theta)
    x=np.concatenate([ring_x,ring_x,[cx,cx]])
    y=np.concatenate([ring_y,ring_y,[cy,cy]])
    z=np.concatenate([np.zeros(segments),np.full(segments,height),[0.,height]])
    faces_i=[];faces_j=[];faces_k=[]
    for k in range(segments):
        nxt=(k+1)%segments
        # 2 triangles per lateral face and one triangle on each end cap.
        faces_i.extend([k,nxt,2*segments,2*segments+1])
        faces_j.extend([nxt,segments+nxt,k,segments+k])
        faces_k.extend([segments+k,segments+k,nxt,segments+nxt])
    return x,y,z,faces_i,faces_j,faces_k


def build_battery_pack_3d(cells,metric='Cell voltage (V)',selected_cell=None):
    """Plotly WebGL model with orbit/zoom/hover and a highlighted cell."""
    if cells.empty:raise ValueError('Cannot render a battery pack without cells.')
    if metric not in BATTERY_3D_SCALES:raise ValueError('Unknown 3D battery metric.')
    lo,hi,colorscale=BATTERY_3D_SCALES[metric]
    field={
        'Cell voltage (V)':'voltage_v',
        'Temperature proxy (°C)':'temperature_proxy_c',
        'Pack SOC (%)':'soc_pct',
        'Cell voltage margin (V)':'voltage_margin_v',
    }[metric]
    fig=go.Figure()
    for j,r in enumerate(cells.itertuples(index=False)):
        val=float(getattr(r,field))
        x,y,z,ii,jj,kk=battery_cylinder_mesh(r.x,r.y)
        tooltip=(
            f'<b>{r.cell_id}</b><br>'
            f'Series group {r.series_group} | Parallel {r.parallel_cell}<br>'
            f'Group voltage estimate: {r.voltage_v:.3f} V<br>'
            f'Pack SOC: {r.soc_pct:.1f}%<br>'
            f'Illustrative cell temperature: {r.temperature_proxy_c:.1f} °C<br>'
            f'Voltage margin to 3.20 V: {r.voltage_margin_v:+.3f} V<br>'
            f't = {r.pack_time_s:.1f} s'
        )
        fig.add_trace(go.Mesh3d(
            x=x,y=y,z=z,i=ii,j=jj,k=kk,
            intensity=[val]*len(x),intensitymode='vertex',
            colorscale=colorscale,cmin=lo,cmax=hi,
            flatshading=False,opacity=.96,
            showscale=(j==0),
            colorbar=dict(title=dict(text=metric),len=.70,thickness=13,
                          x=1.01,tickfont=dict(size=10,color='#d8ffe9')) if j==0 else None,
            lighting=dict(ambient=.68,diffuse=.75,specular=.35,roughness=.45,fresnel=.06),
            lightposition=dict(x=75,y=30,z=120),
            name=r.cell_id,hovertemplate=tooltip+'<extra></extra>',showlegend=False,
        ))
    # Selected cell has a prominent top-ring and pointer; the selection is
    # controlled by the UI, since Mesh3d point-selection is not reliable in
    # Streamlit/Plotly across desktop and mobile versions.
    selected=cells[cells.cell_id==selected_cell]
    if not selected.empty:
        chosen=selected.iloc[0]
        theta=np.linspace(0,2*math.pi,49)
        fig.add_trace(go.Scatter3d(
            x=chosen.x+.62*np.cos(theta),y=chosen.y+.62*np.sin(theta),
            z=np.full(theta.shape,1.48),mode='lines',
            line=dict(color='#ffffff',width=8),showlegend=False,
            name='Selected cell',hoverinfo='skip'))
        fig.add_trace(go.Scatter3d(
            x=[chosen.x],y=[chosen.y],z=[1.75],mode='markers+text',
            marker=dict(size=6,color='#e6faff',symbol='diamond'),
            text=[chosen.cell_id],textposition='top center',
            textfont=dict(color='#ffffff',size=12),hoverinfo='skip',showlegend=False))
    # A simple mounting-tray wireframe gives 3D depth cues. It does not
    # claim to be a battery casing designed to any aircraft dimensions.
    xmin,xmax=float(cells.x.min())-.8,float(cells.x.max())+.8
    ymin,ymax=float(cells.y.min())-.8,float(cells.y.max())+.8
    bx=[xmin,xmax,xmax,xmin,xmin,None,xmin,xmax,xmax,xmin,xmin]
    by=[ymin,ymin,ymax,ymax,ymin,None,ymin,ymin,ymax,ymax,ymin]
    bz=[-.13]*5+[None]+[1.62]*5
    fig.add_trace(go.Scatter3d(x=bx,y=by,z=bz,mode='lines',
        line=dict(color='#5c9f8e',width=3),name='Illustrative enclosure',
        hoverinfo='skip',showlegend=False))
    for xx,yy in [(xmin,ymin),(xmin,ymax),(xmax,ymin),(xmax,ymax)]:
        fig.add_trace(go.Scatter3d(x=[xx,xx],y=[yy,yy],z=[-.13,1.62],
            mode='lines',line=dict(color='#5c9f8e',width=3),
            showlegend=False,hoverinfo='skip'))
    fig.update_layout(
        height=590,margin=dict(l=0,r=15,t=35,b=5),
        title=dict(text='INTERACTIVE BATTERY PACK | REPLAY-DRIVEN',
                   font=dict(color='#caffdf',size=15)),
        paper_bgcolor='#06140f',font=dict(color='#d8ffe9'),
        showlegend=False,uirevision='battery_pack_camera',
        scene=dict(
            bgcolor='#06140f',dragmode='orbit',aspectmode='data',
            xaxis=dict(visible=False,showbackground=False),
            yaxis=dict(visible=False,showbackground=False),
            zaxis=dict(visible=False,showbackground=False),
            camera=dict(eye=dict(x=1.45,y=1.55,z=1.18)),
        ),
    )
    return fig


def render_battery_pack_view(df,config):
    """Streamlit controls are kept independent of the physics time stepping."""
    st.markdown('#### Interactive 3D Battery Pack')
    st.caption('Rotate, zoom and hover to inspect a cell. Choose a cell below to highlight it. '
        'Changing the replay time uses stored battery telemetry, without rerunning the physics simulation.')
    index=st.slider('Flight and battery replay frame',0,len(df)-1,len(df)-1,
                    key='replay_frame')
    frame=df.iloc[index]
    left,right=st.columns(2)
    with left:
        metric=st.selectbox('Color battery geometry by',list(BATTERY_3D_SCALES),
                            key='battery_3d_metric')
    with right:
        p=inferred_parallel_count(config['battery_wh'],config['series_cells'])
        parallel=st.slider('Illustrative cells in parallel (P)',1,6,p,
                           key='battery_3d_parallel')
    gradient=st.slider('Illustrative pack temperature spread (°C)',0.,8.,0.,.5,
                       key='battery_3d_temp_spread')
    cells=representative_battery_cells(frame,config['series_cells'],parallel,
        thermal_spread_c=gradient,nominal_wh=config['battery_wh'])
    chosen=st.selectbox('Highlight / inspect cell',cells.cell_id.tolist(),
                        key='battery_3d_selected')
    fig=build_battery_pack_3d(cells,metric,chosen)
    st.plotly_chart(fig,use_container_width=True,
        config={'displaylogo':False,'responsive':True,'scrollZoom':True})
    c=cells.loc[cells.cell_id==chosen].iloc[0]
    st.caption(f'Replay t = {frame.time_s:.2f} s | {config["series_cells"]}S{parallel}P illustrative geometry | '
        f'{len(cells)} visual cells | implied cell capacity {c.implied_cell_capacity_ah:.2f} Ah '
        'at nominal 3.7 V/cell.')
    metrics_grid([
        ('Pack SOC',f'{frame.battery_soc*100:.1f}%'),
        ('Pack current',f'{frame.battery_current_a:.2f} A'),
        ('Pack voltage',f'{frame.battery_terminal_v:.2f} V'),
        ('Pack thermal state',f'{frame.battery_temperature_c:.1f} °C'),
    ])
    st.markdown(f'**Selected {chosen}** | Series group {int(c.series_group)} | '
        f'Voltage {c.voltage_v:.3f} V | Margin {c.voltage_margin_v:+.3f} V | '
        f'Illustrative cell temperature {c.temperature_proxy_c:.1f} °C')
    if bool(frame.battery_limited) or c.voltage_margin_v<=.05:
        st.warning('Power limiting or low-voltage margin is present in this battery-pack frame.')
    if 'DEGRADED_CELL' in str(frame.battery_status):
        st.warning('Degraded-cell fault enabled. The existing pack model does not identify '
                   'a specific failed cell or simulate independent cell aging.')
    st.info('Model fidelity: pack-level 1-RC Thevenin or ideal-energy simulation. '
        'Displayed series-group voltages are constrained interpolations between the '
        'pack-level estimated minimum and maximum cell voltages. Parallel cells '
        'share group voltage. All cells show pack SOC and SOH. Any nonzero temperature '
        'spread is display-only, not computed heat transfer. Cell geometry and '
        'series/parallel topology are illustrative, not manufacturer-verified.')
    st.download_button('Download representative 3D cell-state table (CSV)',
        cells.drop(columns=['x','y','z']).to_csv(index=False).encode('utf-8'),
        f'battery_pack_replay_{frame.time_s:.1f}s.csv','text/csv')
    return index


# ============================================================================
# QUATERNION-DRIVEN AIRCRAFT GEOMETRY / PLOTLY WEBGL REPLAY
# ============================================================================
# Procedural illustration, not manufacturer CAD. Body axes: +x forward,
# +y right, +z DOWN. q rotates body -> NED; Plotly scene is East/North/UP.
# Control surface and propeller motion are visualization proxies, not
# independently simulated hinge dynamics or blade RPM measurements.

AIRCRAFT_PALETTE = {
    'fuselage': '#d1e4e6', 'canopy': '#3caeec', 'wing': '#8eb1c0',
    'aileron': '#17e3ad', 'tail': '#79a6b7', 'elevator': '#eea955',
    'fin': '#829aa7', 'rudder': '#f18db4', 'motor': '#c8d8dc',
}


def aircraft_body_to_scene(quaternion):
    """Rotation for column vectors in (east, north, up) coordinates."""
    ned_to_enu = np.array([[0., 1., 0.], [1., 0., 0.], [0., 0., -1.]])
    return ned_to_enu @ body_to_ned(qnormalize(quaternion))


def transform_aircraft_points(body_xyz, row, scale=1.):
    points = np.asarray(body_xyz, dtype=float).reshape(-1, 3)
    q = [float(row.qw), float(row.qx), float(row.qy), float(row.qz)]
    center = np.array([float(row.east_m), float(row.north_m), float(row.altitude_m)])
    return center + (float(scale) * points) @ aircraft_body_to_scene(q).T


def make_aircraft_part(name, vertices, faces, color, **extras):
    return dict(name=name, v=np.asarray(vertices, float),
                f=np.asarray(faces, int), color=color, **extras)


def wing_slab(name, root_front, root_rear, tip_front, tip_rear,
              y_root, y_tip, z_root, z_tip, thickness, color,
              hinge=None, hinge_deflection_rad=0.):
    """Tapered low-order slab. Optional hinge rotation about local span axis."""
    points=np.array([
        [root_front,y_root,z_root-thickness/2],
        [root_rear,y_root,z_root-thickness/2],
        [tip_rear,y_tip,z_tip-thickness/2],
        [tip_front,y_tip,z_tip-thickness/2],
        [root_front,y_root,z_root+thickness/2],
        [root_rear,y_root,z_root+thickness/2],
        [tip_rear,y_tip,z_tip+thickness/2],
        [tip_front,y_tip,z_tip+thickness/2],
    ],dtype=float)
    if hinge is not None and abs(hinge_deflection_rad)>1e-12:
        # Hinge x varies linearly over the tapered panel's span.
        h_root,h_tip=hinge
        t=np.clip((points[:,1]-y_root)/(y_tip-y_root),0.,1.)
        hx=h_root+(h_tip-h_root)*t
        dz=points[:,2]-(z_root+(z_tip-z_root)*t)
        dx=points[:,0]-hx
        c,s=math.cos(hinge_deflection_rad),math.sin(hinge_deflection_rad)
        points[:,0]=hx+c*dx+s*dz
        points[:,2]=(z_root+(z_tip-z_root)*t)-s*dx+c*dz
    faces=np.array([
        [0,1,2],[0,2,3],[4,6,5],[4,7,6],
        [0,4,5],[0,5,1],[1,5,6],[1,6,2],
        [2,6,7],[2,7,3],[3,7,4],[3,4,0]
    ],dtype=int)
    return make_aircraft_part(name,points,faces,color)


def lofted_hull(name, x_rings, ry_rings, rz_rings, color, sides=10, z_offset=0.):
    rings=[]
    for x,ry,rz in zip(x_rings,ry_rings,rz_rings):
        for a in np.linspace(0,2*math.pi,sides,endpoint=False):
            rings.append((x,ry*math.cos(a),z_offset+rz*math.sin(a)))
    faces=[]
    for k in range(len(x_rings)-1):
        for j in range(sides):
            a=k*sides+j;b=k*sides+(j+1)%sides
            c=(k+1)*sides+j;d=(k+1)*sides+(j+1)%sides
            faces.extend([(a,b,c),(b,d,c)])
    return make_aircraft_part(name,rings,faces,color)


def cylinder_z(name,cx,cy,z0,z1,r,color,sides=9):
    vertices=[]
    for z in (z0,z1):
        for a in np.linspace(0,2*math.pi,sides,endpoint=False):
            vertices.append((cx+r*math.cos(a),cy+r*math.sin(a),z))
    faces=[]
    for j in range(sides):
        nj=(j+1)%sides
        faces += [(j,nj,sides+j),(nj,sides+nj,sides+j)]
    return make_aircraft_part(name,vertices,faces,color)


def vertical_fin(name, x_front, x_rear, x_front_tip, x_rear_tip,
                 z_root, z_tip, thickness, color,
                 hinge=None, rudder_rad=0.):
    vertices=np.array([
        [x_front,-thickness/2,z_root],[x_rear,-thickness/2,z_root],
        [x_rear_tip,-thickness/2,z_tip],[x_front_tip,-thickness/2,z_tip],
        [x_front,thickness/2,z_root],[x_rear,thickness/2,z_root],
        [x_rear_tip,thickness/2,z_tip],[x_front_tip,thickness/2,z_tip]],float)
    if hinge is not None and abs(rudder_rad)>1e-12:
        h0,h1=hinge
        t=np.clip((vertices[:,2]-z_root)/(z_tip-z_root),0.,1.)
        hx=h0+(h1-h0)*t
        dx=vertices[:,0]-hx;dy=vertices[:,1]
        c,s=math.cos(rudder_rad),math.sin(rudder_rad)
        vertices[:,0]=hx+c*dx-s*dy
        vertices[:,1]=s*dx+c*dy
    faces=[(0,1,2),(0,2,3),(4,6,5),(4,7,6),
           (0,4,5),(0,5,1),(1,5,6),(1,6,2),
           (2,6,7),(2,7,3),(3,7,4),(3,4,0)]
    return make_aircraft_part(name,vertices,faces,color)


def aircraft_3d_parts(profile, row, aircraft_name=''):
    """Procedural mesh set plus line segments, all in aircraft body frame."""
    span=float(profile.get('wingspan_m',DEFAULT_SIZE_M.get(aircraft_name,1.)))
    if profile['type']=='rotor':
        span=max(.30, float(DEFAULT_SIZE_M.get(aircraft_name,.8)))
    length=max(.20,span*(.70 if profile['type']=='fixed' else .40))
    parts=[]; extra=[]
    aileron=clamp(float(row.aileron_actual),-.65,.65)
    elevator=clamp(float(row.elevator_actual),-.65,.65)
    rudder=clamp(float(row.rudder_actual),-.65,.65)
    phase=float(row.time_s)*3.17  # apparent rotation, not actual rotor RPM
    if profile['type']=='fixed':
        parts.append(lofted_hull('Fuselage',
            [-.55*length,-.38*length,-.06*length,.25*length,.53*length],
            [.018,.095,.125,.092,.005],
            [.018,.093,.108,.082,.005],AIRCRAFT_PALETTE['fuselage']))
        parts.append(lofted_hull('Cockpit fairing',
            [.07*length,.19*length,.36*length,.42*length],
            [.040,.072,.047,.002],[.03,.055,.033,.002],
            AIRCRAFT_PALETTE['canopy'],z_offset=-.078*length))
        half=.5*span
        for side in (-1,1):
            yr=side*.09*span;ym=side*.34*span;yt=side*.49*span
            z0=-.018*span;zm=-.045*span;zt=-.056*span
            # Main wing has a separate outer trailing-edge aileron.
            parts.append(wing_slab('Main wing',.15*length,-.15*length,
                .015*length,-.095*length,yr,ym,z0,zm,.018*span,
                AIRCRAFT_PALETTE['wing']))
            parts.append(wing_slab('Outer wing',.015*length,-.056*length,
                -.075*length,-.116*length,ym,yt,zm,zt,.014*span,
                AIRCRAFT_PALETTE['wing']))
            # Hinged at the rear of the fixed outer-wing section.
            parts.append(wing_slab('Aileron',-.056*length,-.095*length,
                -.116*length,-.144*length,ym,yt,zm,zt,.010*span,
                AIRCRAFT_PALETTE['aileron'],hinge=(-.056*length,-.116*length),
                hinge_deflection_rad=.48*aileron*(1 if side>0 else -1)))
            yr=side*.038*span;yt=side*.205*span
            parts.append(wing_slab('Horizontal stabilizer',-.33*length,-.45*length,
                -.41*length,-.485*length,yr,yt,0.,-.006*span,
                .012*span,AIRCRAFT_PALETTE['tail']))
            parts.append(wing_slab('Elevator',-.45*length,-.50*length,
                -.485*length,-.52*length,yr,yt,0.,-.006*span,
                .008*span,AIRCRAFT_PALETTE['elevator'],
                hinge=(-.45*length,-.485*length),
                hinge_deflection_rad=.40*elevator))
        parts.append(vertical_fin('Vertical stabilizer',
            -.32*length,-.47*length,-.43*length,-.48*length,
            -.01*span,-.17*span,.016*span,AIRCRAFT_PALETTE['fin']))
        parts.append(vertical_fin('Rudder',-.47*length,-.53*length,
            -.48*length,-.515*length,-.01*span,-.17*span,
            .010*span,AIRCRAFT_PALETTE['rudder'],
            hinge=(-.47*length,-.48*length),rudder_rad=.4*rudder))
        prop_x=(-.56 if 'MQ-' in aircraft_name else .55)*length
        blade_r=.13*span
        for k in range(2):
            a=phase+k*math.pi
            extra.append([(prop_x,0.,0.),(prop_x,blade_r*math.cos(a),blade_r*math.sin(a))])
        extra.append([(prop_x-.025*length,0.,0.),(prop_x+.025*length,0.,0.)])
    else:
        parts.append(lofted_hull('Central avionics body',
            [-.50*length,-.32*length,.15*length,.49*length],
            [.01,.18*span,.16*span,.01],
            [.01,.11*span,.13*span,.01],AIRCRAFT_PALETTE['fuselage']))
        count=8 if 'Alta 8' in aircraft_name else 4
        radius=.41*span
        zhub=-.10*span
        for k in range(count):
            a=2*math.pi*(k+.5)/count
            cx=radius*math.cos(a);cy=radius*math.sin(a)
            extra.append([(0.,0.,-.025*span),(cx,cy,zhub)])
            parts.append(cylinder_z('Rotor motor',cx,cy,zhub-.035*span,
                                    zhub+.02*span,.038*span,
                                    AIRCRAFT_PALETTE['motor']))
            blade_radius=(.23 if count==4 else .14)*span
            for blade in range(2):
                theta=phase*(1 if k%2 else -1)+blade*math.pi
                extra.append([(cx,cy,zhub-.045*span),
                    (cx+blade_radius*math.cos(theta),
                     cy+blade_radius*math.sin(theta),zhub-.045*span)])
        # Landing skids are fixed visualization geometry.
        for sgn in (-1,1):
            y=sgn*.17*span
            extra.extend([[( -.22*span,y,.11*span),(.22*span,y,.11*span)],
                          [(-.14*span,y,.00*span),(-.14*span,y,.11*span)],
                          [(.14*span,y,.00*span),(.14*span,y,.11*span)]])
    return parts,extra,span


def aircraft_dynamic_traces(profile, row, aircraft_name, visual_scale=1.,
                            show_axes=True,show_thrust=True):
    parts,segments,span=aircraft_3d_parts(profile,row,aircraft_name)
    traces=[]
    for part in parts:
        verts=transform_aircraft_points(part['v'],row,visual_scale)
        tri=part['f']
        traces.append(go.Mesh3d(x=verts[:,0],y=verts[:,1],z=verts[:,2],
            i=tri[:,0],j=tri[:,1],k=tri[:,2],name=part['name'],
            color=part['color'],flatshading=True,opacity=.97,
            lighting=dict(ambient=.66,diffuse=.7,roughness=.65,specular=.18),
            showlegend=False,hovertemplate=part['name']+'<extra></extra>'))
    def scene_lines(body_segments,name,color,width=6):
        flat=[]
        for segment in body_segments:
            flat.extend([*segment,[np.nan,np.nan,np.nan]])
        coords=transform_aircraft_points(flat,row,visual_scale)
        return go.Scatter3d(x=coords[:,0],y=coords[:,1],z=coords[:,2],
            mode='lines',line=dict(width=width,color=color),name=name,
            showlegend=False,hoverinfo='skip')
    traces.append(scene_lines(segments,'Propellers / rotor arms (illustrative)','#d5fafa',6))
    if show_axes:
        for name,axis,color in [('+X forward',[1,0,0],'#2de5be'),
                                ('+Y right',[0,1,0],'#ffb65c'),
                                ('+Z down',[0,0,1],'#f185ac')]:
            end=np.asarray(axis,float)*span*.65
            traces.append(scene_lines([[[0.,0.,0.],end]],name,color,4))
    if show_thrust:
        direction=np.array([1,0,0] if profile['type']=='fixed' else [0,0,-1],float)
        thrust_ratio=clamp(float(row.thrust_n)/max(1.,float(row.mass_kg)*G),0.,2.5)
        endpoint=direction*span*(.25+.40*thrust_ratio)
        traces.append(scene_lines([[[0,0,0],endpoint]],'Thrust vector (magnitude scaled)','#f5d06b',9))
    # Fixed trace count for any given aircraft and visualization toggles.
    return traces,span


def aircraft_follow_eye(row, camera_mode):
    """Camera relative to heading, with a stable world-up horizon.

    Chase sits aft/above/port; inspection looks from front-port above.
    Roll and pitch still rotate the airframe but do not spin the camera.
    Plotly eye is a dimensionless vector relative to the scene center.
    """
    yaw=math.radians(float(row.yaw_deg))
    heading_quat=q_from_euler(0.,0.,yaw)
    relative=(np.array([-1.65,-0.60,-0.80]) if camera_mode=='Chase follow'
              else np.array([1.25,-1.65,-1.25]))
    world=aircraft_body_to_scene(heading_quat) @ relative
    world=2.05*world/max(1e-12,float(np.linalg.norm(world)))
    return dict(x=float(world[0]),y=float(world[1]),z=float(world[2]))


def aircraft_scene_axes(df, row, waypoints, span, scale, camera_mode,
                        camera_zoom=1.,compact=True):
    """Follow-camera axes stay centered on the current aircraft location."""
    center=np.array([float(row.east_m),float(row.north_m),float(row.altitude_m)])
    overview=camera_mode=='Mission overview'
    if not overview:
        # Airframe span occupies ~35-55% of the viewport, even on mobile.
        width=max(1.,span*scale*(1.62 if camera_mode=='Chase follow' else 1.12)
                  *clamp(camera_zoom,.6,3.))
        low=center-width; high=center+width
        # Do NOT clip at altitude zero: it would move the camera center.
        xlo,ylo,zlo=low; xhi,yhi,zhi=high
        eye=aircraft_follow_eye(row,camera_mode)
    else:
        arrays=[(df.east_m.to_numpy(),df.north_m.to_numpy(),df.altitude_m.to_numpy())]
        if waypoints:
            arrays.append(tuple(np.array([w[j] for w in waypoints])
                                for j in (1,0,2)))
        pts=np.concatenate([np.column_stack(a) for a in arrays],axis=0)
        lo=np.min(pts,axis=0);hi=np.max(pts,axis=0)
        margin=max(15.,span*scale*.75)
        xlo,ylo,zlo=lo-margin
        xhi,yhi,zhi=hi+margin
        eye=dict(x=1.50,y=-1.85,z=1.30)
    rng=np.array([xhi-xlo,yhi-ylo,zhi-zlo]);denom=max(float(np.max(rng)),.001)
    def axis(title,low,high):
        return dict(title=title,range=[float(low),float(high)],color='#a7c5bc',
                    gridcolor='#1b483b',backgroundcolor='#081a14',
                    showbackground=bool(overview),
                    showticklabels=bool(overview and not compact),
                    showgrid=bool(overview),zeroline=False)
    return dict(
        xaxis=axis('East (m)',xlo,xhi),
        yaxis=axis('North (m)',ylo,yhi),
        zaxis=axis('Altitude (m)',zlo,zhi),
        aspectmode='manual',
        aspectratio=dict(x=float(rng[0]/denom),y=float(rng[1]/denom),
                         z=float(rng[2]/denom)),
        camera=dict(eye=eye,up=dict(x=0,y=0,z=1),
                    center=dict(x=0,y=0,z=0),
                    projection=dict(type='perspective')),
        bgcolor='#061610',
        dragmode='orbit',
    )


def aircraft_plotly_twin(df, waypoints, frame_index, profile,
                         aircraft_name='',camera_mode='Chase follow',
                         show_ekf=True,show_axes=True,show_thrust=True,
                         animate=False,max_animation_frames=32,
                         scene_content='Aircraft + trail',camera_zoom=1.,
                         overview_aircraft_pct=17.,compact=True):
    """Procedural quaternion-driven airframe, not manufacturer CAD geometry.

    All mesh geometry is generated from recorded six-DOF telemetry. Close
    views use 1:1 physical scale. The explicit overview scaling is display-
    only and never changes aircraft physics, navigation, or exported data.
    """
    if len(df)==0: raise ValueError('Aircraft replay requires telemetry rows.')
    legacy={'Aircraft focus':'Aircraft inspection'}
    camera_mode=legacy.get(camera_mode,camera_mode)
    if camera_mode not in ('Chase follow','Aircraft inspection','Mission overview'):
        raise ValueError('Unknown 3D camera mode.')
    if scene_content not in ('Aircraft only','Aircraft + trail','Full mission'):
        raise ValueError('Unknown aircraft scene content.')
    frame_index=int(clamp(frame_index,0,len(df)-1))
    row=df.iloc[frame_index]
    _,_,span=aircraft_3d_parts(profile,row,aircraft_name)
    path_extent=max(float(np.ptp(df.east_m)),float(np.ptp(df.north_m)),
                    float(np.ptp(df.altitude_m)),span)
    scale=(clamp((overview_aircraft_pct/100.)*path_extent/span,1.,180.)
           if camera_mode=='Mission overview' else 1.)
    fig=go.Figure()
    # Geometry + historical trajectories. The stride reduces mobile payload;
    # telemetry and mission physics remain untouched.
    render_stride=max(1,math.ceil(len(df)/1100))
    route=df.iloc[::render_stride]
    if route.index[-1]!=df.index[-1]:
        route=pd.concat([route,df.iloc[[-1]]])
    def replay_trail(k):
        sample=df.iloc[:k+1:render_stride]
        if sample.index[-1]!=df.index[k]:
            sample=pd.concat([sample,df.iloc[[k]]])
        return sample
    show_full=scene_content=='Full mission'
    show_trail=scene_content!='Aircraft only'
    full_index=trail_index=ekf_index=None
    if show_full:
        full_index=len(fig.data)
        fig.add_trace(go.Scatter3d(x=route.east_m,y=route.north_m,z=route.altitude_m,
            mode='lines',name='Recorded truth (full run)',
            line=dict(color='#286048',width=3),hoverinfo='skip'))
    if show_trail:
        hist=replay_trail(frame_index)
        trail_index=len(fig.data)
        fig.add_trace(go.Scatter3d(x=hist.east_m,y=hist.north_m,z=hist.altitude_m,
            mode='lines',name='Truth through replay',line=dict(color='#27ff9c',width=8)))
        if show_ekf:
            ekf_index=len(fig.data)
            fig.add_trace(go.Scatter3d(x=hist.est_east_m,y=hist.est_north_m,
                z=hist.est_altitude_m,mode='lines',name='EKF estimated path',
                line=dict(color='#59bfff',width=5,dash='dash')))
    if show_full and waypoints:
        fig.add_trace(go.Scatter3d(x=[w[1] for w in waypoints],
            y=[w[0] for w in waypoints],z=[w[2] for w in waypoints],
            mode='markers+text+lines',
            text=[f'WP-{i+1}' for i in range(len(waypoints))],
            textposition='top center',name='Mission waypoints',
            marker=dict(color='#f6a3d5',size=5),
            line=dict(color='#845d85',width=2,dash='dot')))
    dynamic_offset=len(fig.data)
    dynamic,_=aircraft_dynamic_traces(profile,row,aircraft_name,scale,
                                      show_axes,show_thrust)
    fig.add_traces(dynamic)
    scene=aircraft_scene_axes(df,row,waypoints,span,scale,camera_mode,
                              camera_zoom,compact)
    height=550 if compact else 690
    if animate: height+=75
    fig.update_layout(height=height,
        margin=dict(l=0,r=0,t=2,b=2),
        paper_bgcolor='#061610',font=dict(color='#cbf6e1'),
        scene=scene,showlegend=False,
        uirevision=('overview_orbit' if camera_mode=='Mission overview' else None),
        meta=dict(geometry='Generic illustrative 3D airframe',
            camera_mode=camera_mode,scene_content=scene_content,
            airframe_scale_factor=float(scale),
            scale_is_visual_only=bool(camera_mode=='Mission overview'),
            control_surface_positions='From simulated actuator telemetry',
            propeller_rotation='Illustrative only, no blade RPM model',
            playback='Plotly animation independent of Streamlit shared battery replay'))
    if animate and len(df)>1:
        sample=np.unique(np.r_[np.linspace(0,len(df)-1,
            min(max_animation_frames,len(df)),dtype=int),frame_index])
        # Frame trace indices are derived from actual optional trace positions.
        frame_traces=[i for i in (trail_index,ekf_index) if i is not None]
        frame_traces+=list(range(dynamic_offset,dynamic_offset+len(dynamic)))
        frames=[]
        for k in sample:
            instant=df.iloc[int(k)]
            update=[]
            if trail_index is not None:
                h=replay_trail(int(k))
                update.append(go.Scatter3d(x=h.east_m,y=h.north_m,z=h.altitude_m))
                if ekf_index is not None:
                    update.append(go.Scatter3d(x=h.est_east_m,y=h.est_north_m,
                                               z=h.est_altitude_m))
            moving,_=aircraft_dynamic_traces(profile,instant,aircraft_name,scale,
                                              show_axes,show_thrust)
            update.extend(moving)
            # The chase / inspection camera moves with each animated frame.
            animated_scene=(aircraft_scene_axes(df,instant,waypoints,span,scale,
                                camera_mode,camera_zoom,compact)
                            if camera_mode!='Mission overview' else None)
            frames.append(go.Frame(name=f'f{k}',data=update,traces=frame_traces,
                layout=go.Layout(scene=animated_scene)))
        fig.frames=frames
        steps=[dict(method='animate',label=f'{df.iloc[k].time_s:.0f}s',
                    args=[[f'f{k}'],dict(mode='immediate',
                        frame=dict(duration=0,redraw=True),
                        transition=dict(duration=0))]) for k in sample]
        # Reserve a lower strip for buttons and slider; no overlapping legend.
        fig.update_layout(
            scene_domain=dict(x=[0,1],y=[.24,1.]),
            updatemenus=[dict(type='buttons',direction='left',x=.02,y=.12,
                xanchor='left',yanchor='middle',showactive=False,
                font=dict(size=12),bgcolor='#0e3426',
                buttons=[dict(label='▶ Play',method='animate',args=[None,
                  dict(frame=dict(duration=180,redraw=True),fromcurrent=True,
                       transition=dict(duration=0),mode='immediate')]),
                         dict(label='❚❚ Pause',method='animate',args=[[None],
                  dict(frame=dict(duration=0,redraw=False),
                       transition=dict(duration=0),mode='immediate')])])],
            sliders=[dict(active=int(np.argmin(abs(sample-frame_index))),
                x=.02,y=.035,len=.96,pad=dict(t=1,b=0),steps=steps,
                currentvalue=dict(prefix='Replay ',font=dict(size=12)))],
        )
    return fig


# ============================================================================
# REPLAY / REPORTING
# ============================================================================
def plot_series(telemetry,series,title,yaxis=None,height=290,max_points=1300):
    cols=[k for k in series if k in telemetry.columns]
    if not cols:return
    slim=telemetry[['time_s']+cols].iloc[::max(1,math.ceil(len(telemetry)/max_points))]
    fig=go.Figure()
    palette=['#20f59e','#5bbcff','#ffca68','#e197ff','#ff7777']
    for idx,col in enumerate(cols):
        fig.add_trace(go.Scatter(x=slim.time_s,y=slim[col],mode='lines',
            name=series[col],line=dict(color=palette[idx%len(palette)],width=2)))
    fig.update_layout(height=height,title=title,margin=dict(l=15,r=15,t=45,b=15),
        xaxis_title='Time (s)',yaxis_title=yaxis or '',
        paper_bgcolor='#091811',plot_bgcolor='#091811',font=dict(color='#c3e7d6'),
        legend=dict(orientation='h',y=-.28))
    fig.update_xaxes(gridcolor='#17372a');fig.update_yaxes(gridcolor='#17372a')
    st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False})


def hud_figure(row):
    roll=math.radians(float(row.roll_deg));pitch=float(row.pitch_deg)
    fig=go.Figure()
    fig.update_xaxes(range=[-100,100],visible=False,fixedrange=True)
    fig.update_yaxes(range=[-65,65],visible=False,fixedrange=True,
                     scaleanchor='x',scaleratio=1)
    offset=-pitch*1.25
    dx=95*math.cos(roll);dy=95*math.sin(roll)
    fig.add_shape(type='line',x0=-dx,y0=offset+dy,x1=dx,y1=offset-dy,
                  line=dict(color='#21ff86',width=3))
    for x0,x1 in [(-12,-3),(3,12)]:
        fig.add_shape(type='line',x0=x0,y0=0,x1=x1,y1=0,
                      line=dict(color='#d7fff0',width=3))
    fig.add_shape(type='circle',x0=-2,y0=-2,x1=2,y1=2,
                  line=dict(color='#d7fff0',width=2))
    anno=dict(showarrow=False,font=dict(size=14,color='#21ff86'))
    fig.add_annotation(x=-75,y=47,text=f'IAS<br><b>{row.airspeed_ms:.1f} m/s</b>',**anno)
    fig.add_annotation(x=75,y=47,text=f'ALT<br><b>{row.altitude_m:.0f} m</b>',**anno)
    fig.add_annotation(x=0,y=58,text=f'HEADING <b>{row.yaw_deg:03.0f}°</b>',**anno)
    fig.add_annotation(x=-72,y=-43,text=f'α {row.alpha_deg:+.1f}°<br>ENERGY {row.battery_soc*100:.0f}%',**anno)
    fig.add_annotation(x=0,y=-58,text=f"{'GNSS' if row.gps_valid else 'GNSS LOST'} | "
                       f'NAV {row.position_error_m:.1f} m | {row.envelope_mode}',**anno)
    fig.update_layout(height=440,margin=dict(l=0,r=0,t=2,b=2),
        paper_bgcolor='#06100b',plot_bgcolor='#06100b',showlegend=False)
    return fig


def project_xyz(east,north,altitude,azimuth_deg=42.,elevation_deg=24.):
    az=math.radians(azimuth_deg);el=math.radians(elevation_deg)
    east=np.asarray(east,float);north=np.asarray(north,float);alt=np.asarray(altitude,float)
    depth=math.sin(az)*east+math.cos(az)*north
    return math.cos(az)*east-math.sin(az)*north,math.cos(el)*alt+math.sin(el)*depth


def projected_replay(df,waypoints,frame_index):
    hist=df.iloc[:frame_index+1];cur=df.iloc[frame_index]
    fig=go.Figure()
    ex,ey=project_xyz(hist.east_m,hist.north_m,hist.altitude_m)
    nx,ny=project_xyz(hist.est_east_m,hist.est_north_m,hist.est_altitude_m)
    fig.add_trace(go.Scatter(x=ex,y=ey,name='Truth',mode='lines',line=dict(color='#20f59e',width=4)))
    fig.add_trace(go.Scatter(x=nx,y=ny,name='EKF estimate',mode='lines',
                             line=dict(color='#5bbcff',dash='dash',width=2)))
    if waypoints:
        x,y=project_xyz([p[1] for p in waypoints],[p[0] for p in waypoints],
                        [p[2] for p in waypoints])
        fig.add_trace(go.Scatter(x=x,y=y,mode='markers+lines+text',
             name='Waypoints',text=[f'WP-{i+1}' for i in range(len(waypoints))],
             marker=dict(size=8,color='#f9a8db')))
    x,y=project_xyz([cur.east_m],[cur.north_m],[cur.altitude_m])
    fig.add_trace(go.Scatter(x=x,y=y,mode='markers+text',name='UAV',text=['UAV'],
                             marker=dict(color='#ff7474',size=13,symbol='diamond')))
    fig.update_layout(height=495,paper_bgcolor='#07140d',plot_bgcolor='#07140d',
        font=dict(color='#d8ffe9'),margin=dict(l=0,r=0,t=10,b=5),
        legend=dict(orientation='h',y=-.15))
    return fig


def webgl_replay(df,waypoints,frame_index):
    hist=df.iloc[:frame_index+1];cur=df.iloc[frame_index]
    fig=go.Figure()
    fig.add_trace(go.Scatter3d(x=hist.east_m,y=hist.north_m,z=hist.altitude_m,
        mode='lines',name='Truth',line=dict(color='#20f59e',width=6)))
    fig.add_trace(go.Scatter3d(x=hist.est_east_m,y=hist.est_north_m,z=hist.est_altitude_m,
        mode='lines',name='EKF estimate',line=dict(color='#5bbcff',width=4,dash='dash')))
    if waypoints:
        fig.add_trace(go.Scatter3d(x=[p[1] for p in waypoints],y=[p[0] for p in waypoints],
            z=[p[2] for p in waypoints],mode='lines+markers+text',
            name='Waypoints',text=[f'WP-{i+1}' for i in range(len(waypoints))]))
    fig.add_trace(go.Scatter3d(x=[cur.east_m],y=[cur.north_m],z=[cur.altitude_m],
        mode='markers+text',name='UAV',text=['UAV'],marker=dict(size=7,color='#ff7474')))
    fig.update_layout(height=580,margin=dict(l=0,r=0,t=0,b=0),
        scene=dict(xaxis_title='East (m)',yaxis_title='North (m)',
                   zaxis_title='Altitude (m)',aspectmode='data',
                   bgcolor='#091811'),paper_bgcolor='#091811',font=dict(color='#d8ffe9'))
    return fig


def bundle_zip(result):
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('flight_telemetry.csv',result['telemetry'].to_csv(index=False))
        z.writestr('scenario.json',json.dumps(result['scenario'],indent=2,allow_nan=False))
        if result['swarm']:
            z.writestr('swarm_history.csv',result['swarm']['history'].to_csv(index=False))
            z.writestr('swarm_final.csv',result['swarm']['final'].to_csv(index=False))
        z.writestr('README.txt',
            f'UAV Battery Efficiency Estimator {VERSION}\n'
            'Research simulation only, not for actual aircraft control.\n'
            'Autopilot uses simulated truth state; EKF used for separate navigation analysis.\n'
            'GPT-based control and PX4/ArduPilot connections are not implemented.\n')
    return memory.getvalue()


def theme_css():
    st.markdown('''<style>
    .stApp { background:linear-gradient(125deg,#06100b,#0a1914 65%,#07100c); color:#d8ffe9; }
    h1,h2,h3 { color:#caffdf!important; letter-spacing:0.015em; }
    [data-testid="stMetric"] { background:#0c2319; border:1px solid #21543b;
        border-radius:12px; padding:10px; }
    [data-testid="stMetricLabel"] { color:#8bceb0; }
    [data-testid="stSidebar"] { background:#0a1711; }
    div.stButton > button[kind="primary"] { background:#087d52; color:white; border:1px solid #20f59e; }
    </style>''',unsafe_allow_html=True)


def sidebar_inputs():
    with st.sidebar:
        st.header('01 | Aircraft & Energy')
        names=list(UAV_PROFILES)
        name=st.selectbox('Aircraft profile',names,index=names.index('RQ-20 Puma'))
        profile=UAV_PROFILES[name]
        payload=st.number_input('Payload (g)',min_value=0,
            max_value=int(profile['max_payload_g']),value=0,step=10,key=f'payload_{name}')
        battery_conf=dict(battery_wh=float(profile.get('battery_wh',100.)),
            specific_energy=220.,series_cells=infer_series_cells(float(profile.get('battery_wh',100.))),
            battery_soc=100.,battery_soh=100.,battery_temp=25.,
            max_c_rate=8.,resistance_scale=1.,cell_imbalance_mv=0.,
            degraded_cell=False,reserve_soc=10.,battery_twin=False,fuel_fill=100.)
        if profile['power_system']=='Battery':
            wh=st.number_input('Pack capacity (Wh)',min_value=1.,
                value=float(profile['battery_wh']),step=5.,key=f'battery_{name}')
            battery_conf['battery_wh']=wh
            battery_conf['specific_energy']=st.slider('Specific energy (Wh/kg)',120.,400.,220.,5.,key=f'energy_{name}')
            battery_conf['series_cells']=st.number_input('Series cells (S)',2,24,
                infer_series_cells(wh),step=1,key=f'series_{name}')
            with st.expander('Battery Digital Twin',expanded=True):
                battery_conf['battery_twin']=st.checkbox('Enable non-ideal 1-RC model',True,key=f'btwin_{name}')
                battery_conf['battery_soc']=st.slider('Initial SOC (%)',20.,100.,100.,1.,key=f'soc_{name}')
                battery_conf['battery_soh']=st.slider('Initial SOH (%)',50.,100.,100.,1.,key=f'soh_{name}')
                battery_conf['battery_temp']=st.slider('Initial pack temperature (°C)',-20.,60.,25.,1.,key=f'btemp_{name}')
                battery_conf['max_c_rate']=st.slider('Max continuous C-rate',1.,20.,8. if profile['type']=='rotor' else 6.,.5,key=f'crate_{name}')
                battery_conf['resistance_scale']=st.slider('Resistance multiplier',.5,3.,1.,.1,key=f'rs_{name}')
                battery_conf['cell_imbalance_mv']=st.slider('Cell imbalance (mV)',0.,250.,0.,5.,key=f'imb_{name}')
                battery_conf['degraded_cell']=st.checkbox('Inject degraded cell',False,key=f'cellfault_{name}')
                battery_conf['reserve_soc']=st.slider('Reserve SOC (%)',5.,30.,10.,1.,key=f'reserve_{name}')
        else:
            battery_conf['fuel_fill']=st.slider('Initial fuel load (%)',10.,100.,100.,5.,key=f'fuel_{name}')
            st.caption(f"Fuel {profile['fuel_tank_l']:.0f} L; BSFC {profile['bsfc_gpkwh']:.0f} g/kWh")
        st.caption(f"{profile['power_system']} | {profile['type']} | reference mass {profile['base_weight_kg']:,.2f} kg")
        st.caption(f"Autonomy concept: {profile['ai_capabilities']}")

        st.header('02 | Mission Guidance')
        speed=st.number_input('Commanded airspeed (km/h)',min_value=7.2,
            value=float(DEFAULT_SPEED_KMH[name]),step=1.,key=f'speed_{name}')
        alt=st.number_input('Initial altitude (m)',min_value=5.,value=100.,step=10.)
        duration=st.slider('Simulation duration (min)',1,20,5)
        dt=st.select_slider('Control / telemetry Δt (s)',[.02,.05,.1],value=.05)
        capture=st.slider('Waypoint capture radius (m)',10,120,35)
        waypoints=st.text_area('Waypoint list: north,east,altitude (m)',
            '400,0,120; 700,300,140; 400,650,110; 0,350,100; 0,0,100',height=105)

        st.header('03 | Environment & Disturbances')
        temp=st.number_input('Sea-level temperature (°C)',value=25.,step=1.)
        wind=st.number_input('Wind speed (km/h)',min_value=0.,value=8.,step=1.)
        wind_dir=st.slider('Wind FROM (degrees)',0,359,270)
        turbulence=st.selectbox('Turbulence (correlated gust proxy)',
                                ['None','Light','Moderate','Severe'],index=1)
        turb_seed=st.number_input('Turbulence seed',0,100000,1234)
        clouds=st.slider('Cloud cover (%)',0,100,50)
        humidity=st.slider('Humidity / haze factor',0.,1.,.5,.05)
        background=st.slider('Background complexity',0.,1.,.5,.05)
        stealth=st.checkbox('Apply signature-management drag proxy',True)
        stealth_drag=st.slider('Added drag multiplier',1.,1.5,1.10,.05,disabled=not stealth)
        stealth_drag=stealth_drag if stealth else 1.
        effective_size=st.slider('Visual / IR size (m)',.2,20.,
                                 min(20.,float(DEFAULT_SIZE_M[name])),.1,key=f'size_{name}')

        st.header('04 | Envelope / Safety')
        envelope=st.checkbox('Enable envelope protection',True)
        max_bank=st.slider('Bank angle limit (deg)',20.,55.,35.,1.)
        overspeed_default=float(math.ceil(max(32.,1.4*DEFAULT_SPEED_KMH[name]/3.6)))
        overspeed=st.slider('Overspeed limit (m/s)',15.,200.,overspeed_default,1.,key=f'overspeed_{name}')

        st.header('05 | Sensors / Injected Faults')
        sensor_seed=st.number_input('Sensor seed',0,100000,42)
        gps_dropout=st.checkbox('GNSS dropout',True)
        gps_start=st.number_input('Dropout start (s)',0.,value=90.,step=10.)
        gps_duration=st.number_input('Dropout length (s)',0.,value=45.,step=5.)
        imu_bias=st.checkbox('IMU bias',True)
        baro_bias=st.checkbox('Barometer bias',True)
        motor_fault=st.checkbox('Motor degradation',False)
        motor_start=st.number_input('Motor fault start (s)',0.,value=150.,step=10.,disabled=not motor_fault)
        motor_health=st.slider('Degraded motor health',.35,1.,.75,.05,disabled=not motor_fault)

        st.header('06 | Swarm (Low-order)')
        swarm_enabled=st.checkbox('Enable secondary swarm model',True)
        swarm_size=st.slider('Number of vehicles',1,12,4,disabled=not swarm_enabled)
        swarm_rounds=st.slider('Coordination rounds',1,8,4,disabled=not swarm_enabled)
        swarm_coord=st.checkbox('Role-aware coordination',True,disabled=not swarm_enabled)
        spacing=st.slider('Formation spacing (m)',25.,500.,125.,25.,disabled=not swarm_enabled)
        zone=st.slider('Threat-zone radius (km)',0.,5.,.75,.05,disabled=not swarm_enabled)
        threat_n=st.number_input('Threat-zone North (m)',value=400.,step=50.,disabled=not swarm_enabled)
        threat_e=st.number_input('Threat-zone East (m)',value=300.,step=50.,disabled=not swarm_enabled)
        swarm_reserve=st.slider('Swarm RTB reserve (%)',5.,40.,15.,1.,disabled=not swarm_enabled)
        swarm_seed=st.number_input('Swarm seed',0,100000,2026,disabled=not swarm_enabled)

        run=st.button('Run v0.8.4 Simulation',type='primary',use_container_width=True)
        reset=st.button('Clear Previous Run',use_container_width=True)
    config=dict(aircraft=name,payload_g=payload,speed_kmh=speed,altitude_m=alt,
        duration_min=duration,dt=dt,capture_radius=capture,waypoints=waypoints,
        temp_c=temp,wind_kmh=wind,wind_from=wind_dir,turbulence=turbulence,
        turb_seed=turb_seed,cloud_cover=clouds,humidity=humidity,
        background=background,stealth_drag=stealth_drag,effective_size=effective_size,
        envelope=envelope,max_bank=max_bank,overspeed=overspeed,sensor_seed=sensor_seed,
        gps_dropout=gps_dropout,gps_start=gps_start,gps_duration=gps_duration,
        imu_bias=imu_bias,baro_bias=baro_bias,motor_fault=motor_fault,
        motor_start=motor_start,motor_health=motor_health,swarm_enabled=swarm_enabled,
        swarm_size=swarm_size,swarm_rounds=swarm_rounds,swarm_coordination=swarm_coord,
        swarm_spacing_m=spacing,threat_radius_km=zone,threat_n=threat_n,threat_e=threat_e,
        swarm_reserve=swarm_reserve,swarm_seed=swarm_seed,**battery_conf)
    return config,run,reset


def metrics_grid(entries,per_row=4):
    for offset in range(0,len(entries),per_row):
        columns=st.columns(min(per_row,len(entries)-offset))
        for col,(title,value) in zip(columns,entries[offset:offset+per_row]):
            col.metric(title,value)


def display_report(result):
    df=result['telemetry'];final=result['final'];metrics=result['metrics']
    profile=result['profile'];trim=result['trim'];obs=result['observability']
    scenario=result['scenario'];config=scenario['config']
    st.subheader('Simulation Executive Overview')
    messages=dict(WAYPOINTS_COMPLETE=('success','Waypoint mission completed.'),
        DURATION_LIMIT=('warning','Configured simulation duration reached.'),
        ENERGY_EXHAUSTED=('error','Simulation terminated due to energy exhaustion.'),
        GROUND_CONTACT=('error','Simulation terminated at ground contact.'),
        DYNAMICS_NONFINITE=('error','Simulation terminated: nonfinite dynamics values.'))
    severity,message=messages.get(metrics['status'],('warning',metrics['status']))
    getattr(st,severity)(message)
    if not metrics['trim_converged']:
        st.warning('Trim lift equilibrium not bracketed. Do not interpret this case as a feasible steady flight condition.')
    if not metrics['trim_power_feasible']:
        st.warning('Required trim shaft power exceeds available propulsion power. Results are a power-limited scenario.')
    metrics_grid([
        ('Time',f"{final.time_s/60:.2f} min"),
        ('Energy remaining',f"{final.battery_soc*100:.1f}%"),
        ('Airspeed',f"{final.airspeed_ms:.1f} m/s"),
        ('Altitude',f"{final.altitude_m:.1f} m"),
        ('RMS navigation error',f"{metrics['rms_nav_error_m']:.2f} m"),
        ('Maximum |α|',f"{metrics['max_abs_alpha_deg']:.1f}°"),
        ('Maximum gust',f"{metrics['max_gust_ms']:.1f} m/s"),
        ('Envelope intervention',f"{metrics['envelope_intervention_pct']:.1f}%"),
    ])
    st.subheader('Physics Integrity and Trim')
    metrics_grid([
        ('Initial mass',f"{metrics['initial_mass_kg']:.2f} kg"),
        ('Final mass',f"{metrics['final_mass_kg']:.2f} kg"),
        ('Trim α',f'{trim.alpha_deg:.2f}°'),
        ('Trim elevator',f'{trim.elevator:+.3f}'),
        ('Trim throttle',f'{trim.throttle:.3f}'),
        ('Final thrust',f'{final.thrust_n:.1f} N'),
        ('Max |‖q‖−1|',f"{metrics['max_quaternion_norm_error']:.2e}"),
        ('Power-balance residual',f"{metrics['max_power_residual_w']:.2e} W"),
    ])
    st.caption('Power accounting residual tests delivered electrical terminal power allocation. ' 
        'Airframe aerodynamic parameters, inertia, trim, propulsion, and faults remain generalized assumptions.')
    if profile['power_system']=='Battery':
        st.subheader('Battery Digital Twin')
        b=result['telemetry'].iloc[-1]
        metrics_grid([
            ('Nominal capacity',f'{b.battery_nominal_wh:.1f} Wh'),
            ('Temperature-adjusted',f'{b.battery_temp_adjusted_wh:.1f} Wh'),
            ('SOH-adjusted',f'{b.battery_soh_adjusted_wh:.1f} Wh'),
            ('Usable capacity',f'{b.battery_usable_capacity_wh:.1f} Wh'),
            ('Remaining usable',f'{b.battery_remaining_wh:.1f} Wh'),
            ('SOC',f'{b.battery_soc*100:.1f}%'),
            ('SOH',f'{b.battery_soh*100:.2f}%'),
            ('Terminal voltage',f'{b.battery_terminal_v:.2f} V'),
            ('Current',f'{b.battery_current_a:.1f} A'),
            ('C-rate',f'{b.battery_c_rate:.2f} C'),
            ('Pack temperature',f'{b.battery_temperature_c:.1f} °C'),
            ('Battery status',str(b.battery_status)),
        ])
        replay_index=render_battery_pack_view(df,config)
        tab_energy,tab_voltage,tab_thermal=st.tabs(['Capacity and Power','Voltage and Current','Temperature and Cell Margins'])
        with tab_energy:
            plot_series(df,{'battery_remaining_wh':'Remaining usable energy'},'Capacity depletion','Wh')
            plot_series(df,{'battery_demanded_w':'Demanded','battery_delivered_w':'Delivered',
                            'battery_limit_w':'Available limit'},'Electrical power','W')
            plot_series(df,{'battery_soc':'SOC','battery_soh':'SOH'},'Charge and Health','Fraction')
        with tab_voltage:
            plot_series(df,{'battery_ocv_v':'OCV','battery_terminal_v':'Terminal voltage'},'Voltage sag','V')
            plot_series(df,{'battery_current_a':'Current'},'Pack current','A')
            plot_series(df,{'battery_c_rate':'Discharge rate'},'C-rate','C')
        with tab_thermal:
            plot_series(df,{'battery_temperature_c':'Pack temperature',
                            'ambient_temperature_c':'Ambient'},'Battery thermal state','°C')
            plot_series(df,{'battery_min_cell_v':'Lowest cell','battery_max_cell_v':'Highest cell'},
                        'Simplified cell-voltage envelope','V')
        st.caption('Thermal capacity derating is a reporting proxy; the SOC integrator is charge-based. ' 
            'Remaining usable Wh is not a strict electrical energy-integral balance or a measured BMS estimate.')
    else:
        st.subheader('Fuel / ICE Propulsion')
        metrics_grid([
            ('Fuel remaining',f'{final.fuel_mass_kg:.1f} kg'),
            ('Fuel fraction',f'{final.fuel_fraction*100:.1f}%'),
            ('Shaft power',f'{final.shaft_power_w/1000:.1f} kW'),
            ('Aircraft mass',f'{final.mass_kg:.1f} kg')])
        plot_series(df,{'fuel_mass_kg':'Fuel remaining'},'Fuel depletion','kg')
        plot_series(df,{'engine_shaft_w':'Engine shaft including auxiliaries',
                        'shaft_power_w':'Propeller shaft'},'ICE shaft-power allocation','W')
    st.subheader('Propulsion and Airframe State')
    plot_series(df,{'shaft_power_w':'Propeller / rotor shaft',
                    'power_draw_w':'Battery terminal / ICE engine shaft'},
                'Power conversion','W')
    plot_series(df,{'thrust_n':'Propulsive thrust'},'Thrust time history','N')

    st.subheader('Visual / Infrared Observability Heuristics')
    st.caption('Comparative, unvalidated scores. Not detection probabilities and not based on sensor range, ' 
        'aperture, NETD, radiance propagation, or actual adversary sensor specifications.')
    metrics_grid([
        ('Visual score',f"{obs['visual_score']:.0f}/100"),
        ('IR score',f"{obs['thermal_score']:.0f}/100"),
        ('Blended score',f"{obs['overall_score']:.0f}/100"),
        ('Confidence heuristic',f"{obs['confidence']:.0f}/100"),
    ])
    if result['swarm']:
        st.subheader('Swarm Mission-Layer Study')
        swarm=result['swarm'];sm=swarm['summary']
        metrics_grid([('Vehicles',str(sm['swarm_size'])),('Coordination rounds',str(sm['rounds'])),
            ('Heuristic swarm score',f"{sm['swarm_score']:.1f}/100"),
            ('Energy remaining',f"{sm['mean_energy_pct']:.1f}%"),
            ('Resilience heuristic',f"{sm['resilience_score']:.1f}/100"),
            ('RTB ordered',str(sm['rtb_count']))])
        st.caption('Only the lead vehicle has a full six-DOF and energy model. Others use heuristic propagation.')
        st.dataframe(swarm['final'].round(2),use_container_width=True,hide_index=True)

    st.subheader('Quaternion Aircraft Digital Twin | Plotly 3D')
    # Saved replay index drives the battery visualization, aircraft and HUD.
    if profile['power_system']=='Battery':
        index=replay_index
        st.caption('The battery-pack frame slider also controls the aircraft attitude, control surfaces and HUD.')
    else:
        index=st.slider('Flight / aircraft replay frame',0,len(df)-1,len(df)-1,
                        key='replay_frame')
    frame=df.iloc[index]
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Roll',f'{frame.roll_deg:+.1f}°')
    c2.metric('Pitch',f'{frame.pitch_deg:+.1f}°')
    c3.metric('Yaw / heading',f'{frame.yaw_deg:.1f}°')
    c4.metric('Altitude',f'{frame.altitude_m:.1f} m')
    st.caption(f'Simulation t = {frame.time_s:.2f} s | Waypoint {int(frame.active_waypoint)+1} | '
               f'Actual throttle {frame.throttle_actual*100:.0f}% | '
               f'Quaternion [{frame.qw:+.3f}, {frame.qx:+.3f}, '
               f'{frame.qy:+.3f}, {frame.qz:+.3f}]')
    renderer=st.radio('Aircraft display',
        ['Plotly 3D aircraft mesh (WebGL)','Mobile-safe projected 3D trajectory'],
        horizontal=False,key='aircraft_renderer')
    if renderer.startswith('Plotly'):
        camera_mode=st.selectbox('3D camera',
            ['Chase follow','Aircraft inspection','Mission overview'],
            key='aircraft_camera_v084')
        scene_content=st.selectbox('Scene visibility',
            ['Aircraft only','Aircraft + trail','Full mission'],index=1,
            key='aircraft_scene_content')
        if camera_mode=='Mission overview':
            aircraft_pct=st.slider('Aircraft silhouette as % of mission extent',
                6,26,17,1,key='aircraft_size_pct')
            camera_zoom=1.
            st.caption(f'Overview renders the aircraft larger for readability. '
                       'Physical mass, dimensions, dynamics and recorded route are unchanged.')
        else:
            camera_zoom=st.slider('Camera distance (smaller = closer)',
                .65,2.50,1.0,.05,key='aircraft_camera_zoom')
            aircraft_pct=17.
            st.caption('Airframe shown at physical 1:1 scale. The camera follows '
                       'position and heading, with a stable world-up horizon.')
        with st.expander('Plotly view options',expanded=False):
            show_ekf=st.checkbox('Overlay EKF estimated path',True,
                                 key='aircraft_show_ekf')
            show_axes=st.checkbox('Body reference axes',False,
                                  key='aircraft_show_axes')
            show_thrust=st.checkbox('Thrust vector (scaled)',True,
                                    key='aircraft_show_thrust')
            compact=st.checkbox('Compact chart for iPhone',True,
                                key='aircraft_compact')
            animate=st.checkbox('Enable Plotly Play / Pause',False,
                                 key='aircraft_animation')
        if scene_content=='Full mission':
            st.caption('Route key: green = simulated position, blue dashed = '
                       'EKF estimate, pink WP markers = mission waypoints.')
        elif scene_content=='Aircraft + trail':
            st.caption('Green line = simulated route to current frame; '
                       'blue dashed = EKF estimate (if enabled).')
        else:
            st.caption('Isolated aircraft mesh. No route or waypoints shown.')
        st.caption('Drag to orbit; pinch to zoom. Control surfaces follow simulated '
                   'actuator telemetry. Propeller spin is illustrative.')
        if animate:
            st.info('Play/Pause runs inside the Plotly chart. It does not update '
                    'the Streamlit battery and HUD frame slider. Use the shared '
                    'frame slider above for synchronized inspection.')
        try:
            replay=aircraft_plotly_twin(df,result['waypoints'],index,profile,
                scenario['aircraft'],camera_mode,show_ekf,show_axes,
                show_thrust,animate,max_animation_frames=28,
                scene_content=scene_content,camera_zoom=camera_zoom,
                overview_aircraft_pct=aircraft_pct,compact=compact)
            st.plotly_chart(replay,use_container_width=True,
                config={'displaylogo':False,'responsive':True,'scrollZoom':True})
            actual_scale=float(replay.layout.meta['airframe_scale_factor'])
            st.caption(f'Aircraft mesh: ×{actual_scale:.1f} visualization scale | '
                       f'Mode: {camera_mode} | t={frame.time_s:.1f} s | '
                       f'Roll {frame.roll_deg:+.1f}° | '
                       f'Pitch {frame.pitch_deg:+.1f}° | Yaw {frame.yaw_deg:.1f}°')
        except Exception as exc:
            st.warning(f'Plotly aircraft rendering failed: {exc}. '
                       'Showing the mobile-safe trajectory instead.')
            st.plotly_chart(projected_replay(df,result['waypoints'],index),
                            use_container_width=True,config={'displaylogo':False})
    else:
        st.plotly_chart(projected_replay(df,result['waypoints'],index),
                        use_container_width=True,config={'displaylogo':False})
        st.caption('Mobile-safe projected 3D displays the trajectory without a 3D aircraft mesh.')
    with st.expander('Cockpit HUD for selected frame',expanded=False):
        st.plotly_chart(hud_figure(frame),use_container_width=True,
                        config={'displaylogo':False})
    st.subheader('Flight and Navigation Telemetry')
    tab_att,tab_nav,tab_env=st.tabs(['Attitude / envelope','INS and GNSS / EKF','Environment'])
    with tab_att:
        plot_series(df,{'roll_deg':'Roll','pitch_deg':'Pitch','yaw_deg':'Yaw'},'Euler attitude','degrees')
        plot_series(df,{'alpha_deg':'Angle of attack','alpha_margin_deg':'Stall margin'},
                    'Angle-of-attack protection','degrees')
        plot_series(df,{'throttle_cmd':'Throttle command','throttle_actual':'Actuator'},
                    'Throttle tracking','fraction')
    with tab_nav:
        plot_series(df,{'north_m':'True North','est_north_m':'EKF North'},'Navigation solution','m')
        plot_series(df,{'horizontal_error_m':'Horizontal error',
                        'position_error_m':'3D position error'},'Navigation error','m')
        plot_series(df,{'sigma_north_m':'1σ North covariance',
                        'sigma_altitude_m':'1σ Altitude covariance'},'EKF marginal uncertainties','m')
        st.caption('The control loop uses true simulated state. This EKF output is diagnostic and does ' 
                   'not close the flight-control loop. Gyro attitude lacks a long-term absolute correction.')
    with tab_env:
        plot_series(df,{'rho_kgm3':'Atmospheric density'},'Altitude-varying density','kg/m³')
        plot_series(df,{'gust_n_ms':'North','gust_e_ms':'East',
                        'gust_d_ms':'Down'},'Gust components','m/s')

    with st.expander('Fixed-wing Aerodynamic Coefficient Table'):
        if profile['type']=='fixed':
            st.dataframe(aerodynamic_table(result['params']).round(5),
                         use_container_width=True,hide_index=True)
        else:st.info('Only fixed-wing profiles use these coefficient tables.')

    st.subheader('Telemetry and Scenario Exports')
    dl1,dl2,dl3=st.columns(3)
    with dl1:st.download_button('Telemetry CSV',df.to_csv(index=False).encode(),
                               f'uav_v{VERSION}_telemetry.csv','text/csv',use_container_width=True)
    with dl2:st.download_button('Scenario JSON',json.dumps(scenario,indent=2,allow_nan=False),
                               f'uav_v{VERSION}_scenario.json','application/json',use_container_width=True)
    with dl3:st.download_button('Complete ZIP',bundle_zip(result),
                               f'uav_v{VERSION}_research_bundle.zip','application/zip',use_container_width=True)

    with st.expander('Engineering Interpretation / Validation Limits',expanded=True):
        st.markdown(f'''
**Aircraft:** {scenario['aircraft']}  
**Power system:** {profile['power_system']}  
**Trim:** α {trim.alpha_deg:.2f}°, elevator {trim.elevator:+.3f}, throttle {trim.throttle:.3f}  
**Quaternion propagation:** normalized unit quaternion with 6-DOF rigid-body proxy  
**Navigation:** body-frame specific force, 50-Hz zero-order-held IMU, gyro strapdown, 9-state translational/bias EKF  
**Propulsion:** battery terminal power / ICE shaft power → ESC and motor (if electric) → shaft → propeller/rotor thrust  
**Flight-control feedback:** simulated true state, **not EKF**  
**Battery:** {'ideal reservoir' if not config['battery_twin'] else '1-RC Thevenin-style model' if profile['power_system']=='Battery' else 'not applicable'}  
**3D pack replay:** pack-derived interpolated series voltages and optional display-only thermal spread  
**3D aircraft twin:** true quaternion attitude + position from physics; generic fixed-wing/multicopter Mesh3d silhouettes, actuator-driven deflections, illustrative blade spin  
**Aircraft render modes:** chase-follow camera, close-up inspection (both 1:1 geometry) and mission overview (explicit display-only scale factor). Scene content: aircraft only, trail or complete mission. Plotly Play/Pause is independent of the Streamlit battery slider  
**Turbulence:** first-order correlated Dryden-style approximation, not full spectral Dryden  
**Autopilot deployment:** no onboard controller, MAVLink, PX4, or ArduPilot integration  
**GPT-based interpretation:** conceptual only, not implemented  

Aircraft profiles, inertia, stability derivatives, propulsion maps, motor temperatures, 
cell parameters, visual and IR scores, and swarm behaviors use generic approximations. 
Before any real-world use, require manufacturer-characterized component data, validated 
6-DOF plant, hardware-in-the-loop testing, independent verification, and safety analysis. 
The model does not authorize real flight operations.
''')


def main():
    st.set_page_config(page_title='UAV Battery Efficiency Estimator',layout='wide',
                       page_icon='🛩️')
    theme_css()
    st.title(f'UAV BATTERY EFFICIENCY ESTIMATOR  v{VERSION}')
    st.caption('Fixed-wing / rotor UAV | Energy • Propulsion • Flight Dynamics • ' 
               'Multirate Sensor Emulation • INS/EKF • 3D Battery + Quaternion Aircraft Mesh Replay')
    st.caption('Single-file aerospace research simulator | Built by Tareq Omrani')
    config,run,reset=sidebar_inputs()
    if reset:
        st.session_state.pop('completed_simulation',None)
        st.session_state.pop('replay_frame',None)
        st.success('Previous simulation cleared.')
        st.stop()
    with st.expander('Functional Systems Architecture',expanded='completed_simulation' not in st.session_state):
        st.code('''01 Scenario input → 02 Mass / trim / parameters → 03 Disturbances
04 Waypoint guidance → 05 PID control → 06 Envelope safety → 07 Actuator response
08 Battery / ICE source → 09 Propulsion conversion → 10 Aero + environmental loads
11 Quaternion six-DOF flight plant → 12 Sensor emulation → 13 INS / EKF
14 Timestamped flight record → 15 3D battery / quaternion aircraft Mesh3d twins
16 Flight replay, INS/EKF diagnostics, telemetry and research exports

SIMULATED TRUTH STATE → AUTOPILOT (not EKF feedback)

FUTURE RESEARCH ONLY: Natural language → GPT interpretation → deterministic
command gate → PX4 / ArduPilot. NOT IMPLEMENTED / NOT FLIGHT CONNECTED.''',language='text')
    if run:
        try:
            with st.spinner('Executing coupled flight, propulsion, and sensor simulation...'):
                result=run_physics(config)
            st.session_state['completed_simulation']=result
            st.session_state.pop('replay_frame',None)
        except (ValueError,RuntimeError,FloatingPointError,OverflowError) as exc:
            st.error(f'Simulation could not complete: {exc}')
            st.stop()
    if 'completed_simulation' not in st.session_state:
        st.info('Choose a platform and mission in the sidebar, then select **Run v0.8.4 Simulation**.')
        st.warning('Research use only: generic models, not a certified flight or BMS implementation.')
        st.stop()
    result=st.session_state['completed_simulation']
    previous=result['scenario']['config']
    if config!=previous:
        st.info('Sidebar settings have changed since this run. Select **Run** to update the results.')
    display_report(result)


if __name__=='__main__':
    main()
