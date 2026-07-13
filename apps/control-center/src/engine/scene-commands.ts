import type { SceneDocument, SceneObject, Transform } from "./scene-types";

export type SceneCommand =
  | { kind: "addObject"; object: SceneObject }
  | { kind: "removeObject"; objectId: string }
  | { kind: "updateTransform"; objectId: string; transform: Transform }
  | { kind: "updateGeometry"; objectId: string; geometry: Record<string, unknown> }
  | { kind: "updateMaterial"; objectId: string; material: SceneObject["material"] }
  | { kind: "updatePhysics"; objectId: string; physics: SceneObject["physics"] }
  | { kind: "renameObject"; objectId: string; label: string }
  | { kind: "duplicateObject"; objectId: string; duplicate: SceneObject }
  | { kind: "setParameter"; key: string; value: unknown }
  | { kind: "resetScene"; document: SceneDocument };

export function applySceneCommand(document: SceneDocument, command: SceneCommand): SceneDocument {
  if (command.kind === "resetScene") return command.document;
  if (command.kind === "setParameter") return { ...document, parameters: { ...document.parameters, [command.key]: command.value } };
  if (command.kind === "addObject") return { ...document, objects: [...document.objects, command.object] };
  if (command.kind === "duplicateObject") return { ...document, objects: [...document.objects, command.duplicate] };
  if (command.kind === "removeObject") return { ...document, objects: document.objects.filter((item) => item.id !== command.objectId) };
  return {
    ...document,
    objects: document.objects.map((item) => {
      if (item.id !== command.objectId) return item;
      if (command.kind === "updateTransform") return { ...item, transform: command.transform };
      if (command.kind === "updateGeometry") return { ...item, geometry: command.geometry };
      if (command.kind === "updateMaterial") return { ...item, material: command.material };
      if (command.kind === "updatePhysics") return { ...item, physics: command.physics };
      return { ...item, label: command.label };
    }),
  };
}
