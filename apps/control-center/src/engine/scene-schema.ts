import { z } from "zod";
import { primitiveTypes, type SceneDocument } from "./scene-types";

export const vec3Schema = z.object({ x: z.number().finite(), y: z.number().finite(), z: z.number().finite() });
export const transformSchema = z.object({ position: vec3Schema, rotation: vec3Schema, scale: vec3Schema });
export const materialSchema = z.object({
  color: z.string().regex(/^#[0-9a-f]{6}$/i),
  metalness: z.number().min(0).max(1),
  roughness: z.number().min(0).max(1),
  opacity: z.number().min(0).max(1),
  wireframe: z.boolean(),
  emissive: z.string().regex(/^#[0-9a-f]{6}$/i).optional(),
});
export const physicsSchema = z.object({
  type: z.enum(["fixed", "dynamic", "kinematic"]),
  mass: z.number().nonnegative(),
  restitution: z.number().min(0).max(1),
  friction: z.number().min(0).max(1),
});
export const sceneObjectSchema = z.object({
  id: z.string().min(1),
  type: z.enum(primitiveTypes),
  label: z.string().min(1).max(160),
  transform: transformSchema,
  geometry: z.record(z.string(), z.unknown()),
  material: materialSchema,
  physics: physicsSchema,
  data: z.record(z.string(), z.unknown()),
  metadata: z.record(z.string(), z.unknown()),
  visible: z.boolean(),
});
export const sceneSimulationSchema = z.object({
  simulationId: z.string().min(1),
  adapterId: z.enum(["math.sympy", "physics.simple_projectile", "physics.simple_collision"]),
  status: z.string(),
  inputs: z.record(z.string(), z.unknown()),
  outputs: z.record(z.string(), z.unknown()),
  evidence: z.record(z.string(), z.unknown()),
  attachedObjectIds: z.array(z.string()),
  createdAt: z.string(),
});
export const sceneDocumentSchema = z.object({
  sceneId: z.string().min(1),
  sessionId: z.string().min(1),
  title: z.string().min(1),
  description: z.string(),
  revision: z.string().min(1),
  units: z.record(z.string(), z.unknown()),
  parameters: z.record(z.string(), z.unknown()),
  environment: z.record(z.string(), z.unknown()),
  camera: z.object({ projection: z.enum(["perspective", "orthographic"]), position: vec3Schema, target: vec3Schema }),
  objects: z.array(sceneObjectSchema).max(1000),
  simulations: z.array(sceneSimulationSchema),
  metadata: z.record(z.string(), z.unknown()),
  createdAt: z.string(),
  updatedAt: z.string(),
}) satisfies z.ZodType<SceneDocument>;

export const projectileInputSchema = z.object({ object_id: z.string().min(1), duration: z.number().positive().max(120), time_step: z.number().positive().max(2) });
export const collisionInputSchema = z.object({ object_ids: z.array(z.string().min(1)).length(2), coefficient_of_restitution: z.number().min(0).max(1) });
