from __future__ import annotations

import math
from typing import Any

from ..base import EngineExecutionContext, EngineResult, ResourceEstimate, ScientificEnginePlugin
from ..errors import EngineError
from ..manifest import EngineManifest
from ..registry import EngineRegistry
from ..visualization import validate_visualization


def _number(payload: dict[str, Any], name: str, *, minimum: float | None = None, default: float | None = None) -> float:
    value = payload.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise EngineError("engine_input_invalid", f"{name} must be a finite number.")
    value = float(value)
    if minimum is not None and value < minimum:
        raise EngineError("engine_input_invalid", f"{name} must be at least {minimum}.")
    return value


def _steps(payload: dict[str, Any], *, maximum: int = 2_000) -> tuple[float, int]:
    duration = _number(payload, "duration_seconds", minimum=0.001)
    step = _number(payload, "time_step_seconds", minimum=0.0001, default=0.05)
    count = int(math.ceil(duration / step))
    if count > maximum:
        raise EngineError("engine_resource_limit", f"Requested integration requires more than {maximum} steps.")
    return duration, count


class _Plugin(ScientificEnginePlugin):
    _manifest: EngineManifest
    def manifest(self) -> EngineManifest: return self._manifest
    def estimate(self, payload: dict[str, Any]) -> ResourceEstimate: return ResourceEstimate(self._manifest.expected_resource_class, min(self._manifest.timeout_seconds_default, 5.0))
    def _result(self, **kwargs: Any) -> EngineResult:
        result = EngineResult(**kwargs)
        result.visualization = validate_visualization(result.visualization)
        return result


class MathSympyPlugin(_Plugin):
    _manifest = EngineManifest("math.sympy", "Symbolic math", "1.0.0", "math", "Safe bounded symbolic arithmetic and linear-equation subset.", ("symbolic_math", "evaluate", "solve_linear"), {"type":"object"}, {"type":"object"}, True, False, False, True, False)
    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation = str(payload.get("operation", "evaluate"))
        if operation not in {"evaluate", "substitute", "simplify", "solve_linear"} or not isinstance(payload.get("expression", payload.get("equation")), str):
            raise EngineError("engine_input_invalid", "Provide a supported operation and expression or equation.")
        return {key: value for key, value in payload.items() if key in {"operation", "expression", "equation", "variable", "variables"}}
    def execute(self, payload: dict[str, Any], context: EngineExecutionContext) -> EngineResult:
        from mystic.lab.adapters import run_math_sympy
        response = run_math_sympy(payload)
        if response.get("status") != "completed": raise EngineError("engine_execution_failed", str(response.get("message", "Math engine could not complete.")))
        return self._result(summary={"operation": payload.get("operation", "evaluate")}, values=dict(response.get("outputs", {})), warnings=list(response.get("warnings", [])), assumptions=["Uses Mystic's bounded math grammar or installed SymPy."], evidence=[dict(response.get("evidence", {}))])


class ProjectilePlugin(_Plugin):
    _manifest = EngineManifest("physics.simple_projectile", "Simple projectile", "2.0.0", "physics", "Bounded Newtonian projectile integration without drag.", ("trajectory", "kinematics"), {"type":"object"}, {"type":"object"}, True, False, True, True, True, expected_resource_class="tiny")
    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        duration, _ = _steps(payload)
        position = payload.get("initial_position", [0, 0, 0]); velocity = payload.get("initial_velocity", [0, 0, 0])
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in position) or len(position) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in velocity) or len(velocity) != 3:
            raise EngineError("engine_input_invalid", "initial_position and initial_velocity must contain three finite values.")
        return {"initial_position":[float(v) for v in position], "initial_velocity":[float(v) for v in velocity], "gravity_m_s2":_number(payload,"gravity_m_s2",minimum=0,default=9.80665), "duration_seconds":duration, "time_step_seconds":_number(payload,"time_step_seconds",minimum=0.0001,default=0.05)}
    def execute(self, payload: dict[str, Any], context: EngineExecutionContext) -> EngineResult:
        duration, count = _steps(payload); p = list(payload["initial_position"]); v = list(payload["initial_velocity"]); g = payload["gravity_m_s2"]; dt = duration / count; points=[]
        for index in range(count + 1):
            context.check_cancelled(); t=index*dt; points.append({"t":t,"x":p[0],"y":p[1],"z":p[2]}); p[0]+=v[0]*dt; p[1]+=v[1]*dt-0.5*g*dt*dt; p[2]+=v[2]*dt; v[1]-=g*dt
        return self._result(summary={"final_position":points[-1],"steps":count}, values={"final_position":points[-1],"final_velocity":{"x":v[0],"y":v[1],"z":v[2]}}, series=[{"type":"trajectory","name":"projectile","points":points}], units={"position":"m","velocity":"m/s","time":"s"}, assumptions=["Uniform gravity; air resistance omitted."], visualization={"version":"1","layers":[{"id":"projectile-trajectory","type":"trajectory","label":"Projectile trajectory","visible":True,"data":{"points":points},"style":{},"units":{"position":"m"},"metadata_safe":{}}]})


class CollisionPlugin(_Plugin):
    _manifest = EngineManifest("physics.simple_collision", "One-dimensional collision", "2.0.0", "physics", "Elastic one-dimensional collision for two bounded point masses.", ("collision", "vectors"), {"type":"object"}, {"type":"object"}, True, False, False, True, True)
    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {name:_number(payload,name,minimum=0.000001 if name.startswith("mass") else None) for name in ("mass_a","mass_b","velocity_a","velocity_b")}
    def execute(self, payload: dict[str, Any], context: EngineExecutionContext) -> EngineResult:
        a,b,u,v=(payload[n] for n in ("mass_a","mass_b","velocity_a","velocity_b")); va=((a-b)*u+2*b*v)/(a+b); vb=(2*a*u+(b-a)*v)/(a+b)
        return self._result(summary={"momentum_conserved":True}, values={"velocity_a_m_s":va,"velocity_b_m_s":vb,"momentum_before":a*u+b*v,"momentum_after":a*va+b*vb}, units={"velocity":"m/s","mass":"kg"}, assumptions=["Perfectly elastic, one-dimensional collision."], visualization={"version":"1","layers":[{"id":"collision-vectors","type":"vector","label":"Post-collision velocities","visible":True,"data":{"vectors":[{"id":"a","x":va},{"id":"b","x":vb}]},"style":{},"units":{"velocity":"m/s"},"metadata_safe":{}}]})


class NBodyPlugin(_Plugin):
    _manifest = EngineManifest("physics.n_body", "N-body Newtonian model", "1.0.0", "physics", "Small deterministic Newtonian point-mass integration; not an astrophysical precision model.", ("trajectory", "n_body", "energy_diagnostics"), {"type":"object"}, {"type":"object"}, True, True, True, True, True, expected_resource_class="small", timeout_seconds_default=15, timeout_seconds_max=60)
    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        bodies=payload.get("bodies"); duration,count=_steps(payload,maximum=1_000)
        if not isinstance(bodies,list) or not 2 <= len(bodies) <= 8: raise EngineError("engine_input_invalid","bodies must contain 2 through 8 point masses.")
        clean=[]
        for body in bodies:
            if not isinstance(body,dict) or not isinstance(body.get("id"),str): raise EngineError("engine_input_invalid","Each body needs an ID.")
            mass=_number(body,"mass_kg",minimum=1e-12); position=body.get("position_m"); velocity=body.get("velocity_m_s")
            if not isinstance(position,list) or not isinstance(velocity,list) or len(position)!=3 or len(velocity)!=3: raise EngineError("engine_input_invalid","Bodies require three-dimensional position and velocity.")
            clean.append({"id":body["id"],"mass_kg":mass,"position_m":[float(x) for x in position],"velocity_m_s":[float(x) for x in velocity]})
        return {"bodies":clean,"duration_seconds":duration,"time_step_seconds":duration/count,"gravitational_constant":_number(payload,"gravitational_constant",minimum=1e-20,default=6.67430e-11)}
    def execute(self,payload:dict[str,Any],context:EngineExecutionContext)->EngineResult:
        bodies=[dict(item, position_m=list(item["position_m"]), velocity_m_s=list(item["velocity_m_s"])) for item in payload["bodies"]]; count=round(payload["duration_seconds"]/payload["time_step_seconds"]); dt=payload["time_step_seconds"]; G=payload["gravitational_constant"]; trajectories={b["id"]:[] for b in bodies}
        for step in range(count+1):
            context.check_cancelled()
            for body in bodies: trajectories[body["id"]].append({"t":step*dt,"x":body["position_m"][0],"y":body["position_m"][1],"z":body["position_m"][2]})
            accelerations=[[0.0,0.0,0.0] for _ in bodies]
            for i,a in enumerate(bodies):
                for j,b in enumerate(bodies):
                    if i==j: continue
                    d=[b["position_m"][k]-a["position_m"][k] for k in range(3)]; r2=sum(x*x for x in d)+1e-12; factor=G*b["mass_kg"]/(r2*math.sqrt(r2))
                    for k in range(3): accelerations[i][k]+=factor*d[k]
            for i,body in enumerate(bodies):
                for k in range(3): body["velocity_m_s"][k]+=accelerations[i][k]*dt; body["position_m"][k]+=body["velocity_m_s"][k]*dt
        layers=[{"id":f"trajectory-{bid}","type":"trajectory","label":bid,"visible":True,"data":{"points":points},"style":{},"units":{"position":"m"},"metadata_safe":{}} for bid,points in trajectories.items()]
        return self._result(summary={"body_count":len(bodies),"steps":count,"accuracy":"bounded educational integration"}, values={"final_states":bodies}, series=[{"type":"trajectory","name":bid,"points":points} for bid,points in trajectories.items()], warnings=["Not high-precision astrophysical integration."], units={"position":"m","time":"s"}, visualization={"version":"1","layers":layers})


class KineticsPlugin(_Plugin):
    _manifest = EngineManifest("chemistry.reaction_kinetics", "Reaction kinetics", "1.0.0", "chemistry", "Deterministic mass-action ODE model without laboratory procedure guidance.", ("kinetics", "time_series"), {"type":"object"}, {"type":"object"}, True, False, True, True, True, expected_resource_class="small")
    def validate_input(self,payload:dict[str,Any])->dict[str,Any]:
        species=payload.get("species"); reactions=payload.get("reactions"); duration,count=_steps(payload)
        if not isinstance(species,dict) or not species or not all(isinstance(k,str) and isinstance(v,(int,float)) and v>=0 for k,v in species.items()) or not isinstance(reactions,list) or not reactions: raise EngineError("engine_input_invalid","Provide non-negative species concentrations and reactions.")
        cleaned=[]
        for reaction in reactions:
            if not isinstance(reaction,dict) or not isinstance(reaction.get("rate_constant"),(int,float)) or reaction["rate_constant"]<0 or not isinstance(reaction.get("reactants"),dict) or not isinstance(reaction.get("products"),dict): raise EngineError("engine_input_invalid","Each reaction needs bounded reactants, products, and rate_constant.")
            if not set(reaction["reactants"])|set(reaction["products"]) <= set(species): raise EngineError("engine_input_invalid","Reactions may only reference declared species.")
            cleaned.append(reaction)
        return {"species":{k:float(v) for k,v in species.items()},"reactions":cleaned,"duration_seconds":duration,"time_step_seconds":duration/count}
    def execute(self,payload:dict[str,Any],context:EngineExecutionContext)->EngineResult:
        values=dict(payload["species"]); dt=payload["time_step_seconds"]; count=round(payload["duration_seconds"]/dt); series={name:[] for name in values}
        for step in range(count+1):
            context.check_cancelled()
            for name in values: series[name].append({"t":step*dt,"value":values[name]})
            delta={name:0.0 for name in values}
            for reaction in payload["reactions"]:
                rate=float(reaction["rate_constant"])
                for name,power in reaction["reactants"].items(): rate*=max(values[name],0.0)**float(power)
                for name,coefficient in reaction["reactants"].items(): delta[name]-=float(coefficient)*rate*dt
                for name,coefficient in reaction["products"].items(): delta[name]+=float(coefficient)*rate*dt
            for name in values: values[name]=max(0.0,values[name]+delta[name])
        return self._result(summary={"species":len(values),"model":"mass_action_ode"}, values={"final_concentrations":values}, series=[{"type":"time_series","name":name,"points":points} for name,points in series.items()], units={"concentration":"model-specified","time":"s"}, assumptions=["Numerical Euler integration; no laboratory procedure is represented."], visualization={"version":"1","layers":[{"id":"kinetics-series","type":"time_series_link","label":"Concentration over time","visible":True,"data":{"series":series},"style":{},"units":{"time":"s"},"metadata_safe":{}}]})


class PopulationPlugin(_Plugin):
    _manifest = EngineManifest("biology.population_dynamics", "Population dynamics", "1.0.0", "biology", "Deterministic logistic and Lotka–Volterra population models.", ("population", "time_series", "equilibrium"), {"type":"object"}, {"type":"object"}, True, False, True, True, True)
    def validate_input(self,payload:dict[str,Any])->dict[str,Any]:
        model=str(payload.get("model","logistic")); duration,count=_steps(payload)
        if model=="logistic": return {"model":model,"initial_population":_number(payload,"initial_population",minimum=0),"growth_rate":_number(payload,"growth_rate"),"carrying_capacity":_number(payload,"carrying_capacity",minimum=1e-12),"duration_seconds":duration,"time_step_seconds":duration/count}
        if model=="lotka_volterra": return {"model":model,**{name:_number(payload,name,minimum=0) for name in ("prey_initial","predator_initial","prey_growth","predation","predator_efficiency","predator_death")},"duration_seconds":duration,"time_step_seconds":duration/count}
        raise EngineError("engine_input_invalid","model must be logistic or lotka_volterra.")
    def execute(self,payload:dict[str,Any],context:EngineExecutionContext)->EngineResult:
        dt=payload["time_step_seconds"]; count=round(payload["duration_seconds"]/dt)
        if payload["model"]=="logistic":
            population=payload["initial_population"]; points=[]
            for i in range(count+1): context.check_cancelled(); points.append({"t":i*dt,"value":population}); population=max(0,population+payload["growth_rate"]*population*(1-population/payload["carrying_capacity"])*dt)
            return self._result(summary={"equilibrium":payload["carrying_capacity"]},values={"final_population":population},series=[{"type":"time_series","name":"population","points":points}],units={"time":"s","population":"individuals"},visualization={"version":"1","layers":[{"id":"population","type":"time_series_link","label":"Population","visible":True,"data":{"points":points},"style":{},"units":{},"metadata_safe":{}}]})
        prey,predator=payload["prey_initial"],payload["predator_initial"]; points=[]
        for i in range(count+1):
            context.check_cancelled(); points.append({"t":i*dt,"prey":prey,"predator":predator}); prey,predator=max(0,prey+(payload["prey_growth"]*prey-payload["predation"]*prey*predator)*dt),max(0,predator+(payload["predator_efficiency"]*prey*predator-payload["predator_death"]*predator)*dt)
        return self._result(summary={"model":"lotka_volterra"},values={"prey":prey,"predator":predator},series=[{"type":"time_series","name":"populations","points":points}],units={"time":"s","population":"individuals"},visualization={"version":"1","layers":[{"id":"populations","type":"time_series_link","label":"Prey and predator","visible":True,"data":{"points":points},"style":{},"units":{},"metadata_safe":{}}]})


class DCCircuitPlugin(_Plugin):
    _manifest = EngineManifest("engineering.dc_circuit", "DC resistor circuit", "1.0.0", "engineering", "Safe low-voltage resistive circuit model using nodal analysis for a source and divider topology.", ("dc_circuit", "nodal_analysis", "graph"), {"type":"object"}, {"type":"object"}, True, False, False, True, True)
    def validate_input(self,payload:dict[str,Any])->dict[str,Any]:
        voltage=_number(payload,"source_voltage_v",minimum=0,default=5); r1=_number(payload,"resistance_top_ohm",minimum=0.001); r2=_number(payload,"resistance_bottom_ohm",minimum=0.001)
        if voltage>60: raise EngineError("engine_input_invalid","Phase 2A supports safe low-voltage models up to 60 V.")
        return {"source_voltage_v":voltage,"resistance_top_ohm":r1,"resistance_bottom_ohm":r2}
    def execute(self,payload:dict[str,Any],context:EngineExecutionContext)->EngineResult:
        v,r1,r2=payload["source_voltage_v"],payload["resistance_top_ohm"],payload["resistance_bottom_ohm"]; current=v/(r1+r2); node=v* r2/(r1+r2)
        values={"node_voltages_v":{"source":v,"divider":node,"ground":0.0},"branch_currents_a":{"R_top":current,"R_bottom":current},"power_w":{"R_top":current*current*r1,"R_bottom":current*current*r2}}
        return self._result(summary={"topology":"voltage_divider","singular":False},values=values,units={"voltage":"V","current":"A","power":"W","resistance":"ohm"},assumptions=["Ideal independent DC source and resistors; safe low-voltage model only."],visualization={"version":"1","layers":[{"id":"dc-divider","type":"graph_network","label":"DC voltage divider","visible":True,"data":{"nodes":[{"id":"source","voltage_v":v},{"id":"divider","voltage_v":node},{"id":"ground","voltage_v":0}],"edges":[{"id":"R_top","from":"source","to":"divider","resistance_ohm":r1},{"id":"R_bottom","from":"divider","to":"ground","resistance_ohm":r2}]},"style":{},"units":{"voltage":"V"},"metadata_safe":{}}]})


def builtin_registry() -> EngineRegistry:
    return EngineRegistry([MathSympyPlugin(), ProjectilePlugin(), CollisionPlugin(), NBodyPlugin(), KineticsPlugin(), PopulationPlugin(), DCCircuitPlugin()])
