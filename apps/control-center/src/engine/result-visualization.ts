import type { SceneSimulation, Vec3 } from "./scene-types";

export function trajectoryPoints(simulation: SceneSimulation): Vec3[] {
  const trajectory = simulation.outputs.trajectory;
  if (!Array.isArray(trajectory)) return [];
  return trajectory.flatMap((point) => {
    if (typeof point !== "object" || point === null) return [];
    const value = point as Record<string, unknown>;
    return typeof value.x === "number" && typeof value.y === "number" && typeof value.z === "number" ? [{ x: value.x, y: value.y, z: value.z }] : [];
  });
}
