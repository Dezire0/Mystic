import { collisionInputSchema, projectileInputSchema } from "./scene-schema";
import type { SceneObject, Vec3 } from "./scene-types";

export function localProjectilePreview(object: SceneObject, duration: number, step: number, gravity = 9.81): Vec3[] {
  const velocity = object.data.velocity as Partial<Vec3> | undefined;
  const start = object.transform.position;
  const points: Vec3[] = [];
  for (let time = 0; time <= duration + Number.EPSILON; time += step) {
    points.push({ x: start.x + (velocity?.x ?? 0) * time, y: start.y + (velocity?.y ?? 0) * time - 0.5 * gravity * time * time, z: start.z + (velocity?.z ?? 0) * time });
  }
  return points;
}

export function validateSimulationInput(adapterId: string, input: unknown) {
  if (adapterId === "physics.simple_projectile") return projectileInputSchema.parse(input);
  if (adapterId === "physics.simple_collision") return collisionInputSchema.parse(input);
  return input;
}
