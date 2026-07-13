import { describe, expect, it } from "vitest";
import { newPrimitive, parseSceneDocument } from "./scene-document";
import { applySceneCommand } from "./scene-commands";
import { commit, createHistory, redo, undo } from "./scene-history";
import { projectileInputSchema } from "./scene-schema";
import { localProjectilePreview } from "./simulation-adapters";
import type { SceneDocument } from "./scene-types";

function documentFixture(): SceneDocument { return { sceneId: "scene-1", sessionId: "session-1", title: "Fixture", description: "", revision: "1", units: {}, parameters: { gravity: 9.81 }, environment: {}, camera: { projection: "perspective", position: { x: 1, y: 1, z: 1 }, target: { x: 0, y: 0, z: 0 } }, objects: [], simulations: [], metadata: {}, createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z" }; }
describe("Mystic scene engine", () => {
  it("validates a serializable SceneDocument round trip", () => { const original = documentFixture(); const parsed = parseSceneDocument(JSON.parse(JSON.stringify(original))); expect(parsed).toEqual(original); });
  it("adds and transforms objects without renderer state", () => { const object = newPrimitive("box", 1); const added = applySceneCommand(documentFixture(), { kind: "addObject", object }); const changed = applySceneCommand(added, { kind: "updateTransform", objectId: object.id, transform: { ...object.transform, position: { x: 2, y: 3, z: 4 } } }); expect(changed.objects[0].transform.position).toEqual({ x: 2, y: 3, z: 4 }); });
  it("supports bounded undo and redo", () => { const object = newPrimitive("sphere", 1); const history = commit(createHistory(documentFixture(), 2), { kind: "addObject", object }); expect(undo(history).present.objects).toHaveLength(0); expect(redo(undo(history)).present.objects).toHaveLength(1); });
  it("rejects invalid projectile parameters", () => { expect(() => projectileInputSchema.parse({ object_id: "ball", duration: -1, time_step: 0.1 })).toThrow(); });
  it("labels browser projectile paths as local previews", () => { const object = newPrimitive("sphere", 1); object.data.velocity = { x: 2, y: 4, z: 0 }; const path = localProjectilePreview(object, 1, 0.5); expect(path).toHaveLength(3); expect(path[1].y).toBeGreaterThan(path[0].y); });
});
