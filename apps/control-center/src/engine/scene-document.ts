import type { PrimitiveType, SceneDocument, SceneObject, Vec3 } from "./scene-types";
import { sceneDocumentSchema } from "./scene-schema";

export const zero: Vec3 = { x: 0, y: 0, z: 0 };
export const one: Vec3 = { x: 1, y: 1, z: 1 };

export function newPrimitive(type: PrimitiveType, sequence: number): SceneObject {
  const id = `${type}-${crypto.randomUUID().slice(0, 8)}`;
  return {
    id,
    type,
    label: `${type[0].toUpperCase()}${type.slice(1)} ${sequence}`,
    transform: { position: { ...zero }, rotation: { ...zero }, scale: { ...one } },
    geometry: defaultGeometry(type),
    material: { color: "#45d6a8", metalness: 0.08, roughness: 0.58, opacity: 1, wireframe: false },
    physics: { type: type === "plane" ? "fixed" : "dynamic", mass: 1, restitution: 0.25, friction: 0.55 },
    data: {},
    metadata: {},
    visible: true,
  };
}

function defaultGeometry(type: PrimitiveType): Record<string, unknown> {
  if (type === "box") return { width: 1, height: 1, depth: 1 };
  if (type === "sphere") return { radius: 0.5, widthSegments: 24, heightSegments: 16 };
  if (type === "cylinder") return { radiusTop: 0.5, radiusBottom: 0.5, height: 1 };
  if (type === "cone") return { radius: 0.5, height: 1 };
  if (type === "plane") return { width: 10, height: 10 };
  if (type === "line" || type === "arrow") return { end: { x: 1, y: 0, z: 0 } };
  if (type === "label") return { text: "Label" };
  return {};
}

export function parseSceneDocument(input: unknown): SceneDocument {
  return sceneDocumentSchema.parse(input);
}
