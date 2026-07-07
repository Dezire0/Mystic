# Mystic LAB 3D Virtual Lab

## Purpose

The Mystic LAB 3D virtual lab is the scene and interaction layer of the AI Research Lab OS.

Its role is to:

- represent experimental state visually
- attach model plans and engine outputs to scene objects
- support parameterized simulation setup
- provide exportable scene snapshots for reports and future UI rendering

It is not itself the simulation engine.

## Design Principle

Models plan, critique, and interpret.

Simulation engines compute.

The 3D virtual lab visualizes and stores scene state so model agents and users can inspect and manipulate research context.

## Phase 1 Scope

Phase 1 adds a scene API for:

- math and simple physics experiments
- structured object placement
- parameter updates
- simulation attachment
- scene snapshot export

It does not yet ship a full interactive 3D frontend renderer inside the Worker.

Current state:

- implemented for Phase 1 in local mode and public cloud-native Worker mode
- scene state, object state, simulation records, reports, and exports persist in local JSON mode or Supabase mode

## Phase 1 MCP Tools

| Tool | Status |
| --- | --- |
| `create_lab_scene` | Implemented |
| `get_lab_scene` | Implemented |
| `add_lab_object` | Implemented |
| `update_lab_object` | Implemented |
| `remove_lab_object` | Implemented |
| `set_lab_parameters` | Implemented |
| `run_lab_simulation` | Implemented |
| `attach_simulation_to_scene` | Implemented |
| `export_lab_snapshot` | Implemented |
| `generate_lab_report` | Implemented |

If an engine or exporter is unavailable, the tool should return a structured `deferred` or `engine_required` response.

## Scene State Schema

Top-level scene state should include:

- `scene_id`
- `session_id`
- `domain`
- `title`
- `description`
- `units`
- `parameters`
- `objects`
- `attached_simulations`
- `evidence_refs`
- `report_refs`
- `metadata`
- `created_at`
- `updated_at`

### Scene Object Schema

Each object should include:

- `id`
- `type`
- `label`
- `position`
- `rotation`
- `scale`
- `geometry`
- `material`
- `data`
- `metadata`

### Example

```json
{
  "scene_id": "scene-123",
  "session_id": "lab-123",
  "domain": "physics",
  "title": "Projectile baseline",
  "description": "Simple projectile setup for Phase 1.",
  "units": {
    "length": "m",
    "time": "s",
    "mass": "kg"
  },
  "parameters": {
    "gravity": 9.81,
    "air_resistance": false
  },
  "objects": [
    {
      "id": "ball-1",
      "type": "rigid_body",
      "label": "Projectile",
      "position": {"x": 0, "y": 1, "z": 0},
      "rotation": {"x": 0, "y": 0, "z": 0},
      "scale": {"x": 1, "y": 1, "z": 1},
      "geometry": {"kind": "sphere", "radius": 0.1},
      "material": {"color": "#ff7a59"},
      "data": {"mass": 0.2, "velocity": {"x": 5, "y": 8, "z": 0}},
      "metadata": {"source": "user"}
    }
  ],
  "attached_simulations": [],
  "evidence_refs": [],
  "report_refs": [],
  "metadata": {
    "scene_adapter": "scene.three_json"
  }
}
```

## Relationship to Reports and Evidence

Scene objects should be able to reference:

- claims
- experiments
- failures
- simulation outputs
- exported report sections

This allows the scene to be part of the research archive, not just a visualization artifact.

## Storage Direction

Phase 1 should persist scene state in Supabase-compatible records for cloud-native mode, while preserving the local JSON storage path for local mode.

Expected stored objects:

- scene rows
- scene object rows
- simulation rows
- report/export references

## Rendering Direction

The initial scene export target should be a Three.js-friendly JSON representation through `scene.three_json`.

This is an interchange format first, not a claim that a full production 3D viewer already exists.

## Explicit Non-goals

- no home automation
- no IoT device control
- no robotics control
- no lab hardware actuation
- no fake simulation output
