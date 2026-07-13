export const primitiveTypes = [
  "box",
  "sphere",
  "cylinder",
  "cone",
  "plane",
  "line",
  "arrow",
  "point",
  "label",
  "light",
  "camera",
] as const;

export type PrimitiveType = (typeof primitiveTypes)[number];
export type Vec3 = { x: number; y: number; z: number };
export type Transform = { position: Vec3; rotation: Vec3; scale: Vec3 };
export type Material = {
  color: string;
  metalness: number;
  roughness: number;
  opacity: number;
  wireframe: boolean;
  emissive?: string;
};
export type Physics = { type: "fixed" | "dynamic" | "kinematic"; mass: number; restitution: number; friction: number };

export type SceneObject = {
  id: string;
  type: PrimitiveType;
  label: string;
  transform: Transform;
  geometry: Record<string, unknown>;
  material: Material;
  physics: Physics;
  data: Record<string, unknown>;
  metadata: Record<string, unknown>;
  visible: boolean;
};

export type SceneSimulation = {
  simulationId: string;
  adapterId: "math.sympy" | "physics.simple_projectile" | "physics.simple_collision";
  status: string;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  evidence: Record<string, unknown>;
  attachedObjectIds: string[];
  createdAt: string;
};

export type SceneDocument = {
  sceneId: string;
  sessionId: string;
  title: string;
  description: string;
  revision: string;
  units: Record<string, unknown>;
  parameters: Record<string, unknown>;
  environment: Record<string, unknown>;
  camera: { projection: "perspective" | "orthographic"; position: Vec3; target: Vec3 };
  objects: SceneObject[];
  simulations: SceneSimulation[];
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
};

export type SyncStatus = "loading" | "clean" | "dirty" | "saving" | "synced" | "conflict" | "error";
export type SafeErrorCode =
  | "backend_offline"
  | "unauthorized"
  | "session_expired"
  | "scene_not_found"
  | "object_not_found"
  | "scene_conflict"
  | "invalid_scene_document"
  | "simulation_invalid_parameters"
  | "simulation_engine_required"
  | "simulation_failed"
  | "asset_storage_required"
  | "webgl_unavailable"
  | "renderer_failed"
  | "export_failed";
