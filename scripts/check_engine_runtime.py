from __future__ import annotations

import json

from mystic.lab.engines import EngineExecutionContext, builtin_registry


SMOKE_INPUTS = {
    "math.sympy": {"operation":"solve_linear","equation":"2*x + 3 = 7","variable":"x"},
    "physics.simple_projectile": {"initial_position":[0,0,0],"initial_velocity":[1,5,0],"duration_seconds":1},
    "physics.simple_collision": {"mass_a":1,"mass_b":1,"velocity_a":2,"velocity_b":0},
    "physics.n_body": {"bodies":[{"id":"a","mass_kg":1e10,"position_m":[0,0,0],"velocity_m_s":[0,0,0]},{"id":"b","mass_kg":1e5,"position_m":[10,0,0],"velocity_m_s":[0,1,0]}],"duration_seconds":1,"time_step_seconds":0.1},
    "chemistry.reaction_kinetics": {"species":{"A":1,"B":0},"reactions":[{"reactants":{"A":1},"products":{"B":1},"rate_constant":0.2}],"duration_seconds":1},
    "biology.population_dynamics": {"model":"logistic","initial_population":10,"growth_rate":0.2,"carrying_capacity":100,"duration_seconds":1},
    "engineering.dc_circuit": {"source_voltage_v":5,"resistance_top_ohm":1000,"resistance_bottom_ohm":1000},
}


def main() -> int:
    registry=builtin_registry(); outcomes=[]
    for manifest in registry.list():
        plugin=registry.get(manifest.engine_id); payload=plugin.validate_input(SMOKE_INPUTS[manifest.engine_id]); result=plugin.execute(payload, EngineExecutionContext(run_id=f"verify-{manifest.engine_id}")); outcomes.append({"engine_id":manifest.engine_id,"status":"ok","visualization":bool(result.visualization),"deterministic":manifest.deterministic})
    print(json.dumps({"status":"ok","engine_count":len(outcomes),"engines":outcomes},sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
