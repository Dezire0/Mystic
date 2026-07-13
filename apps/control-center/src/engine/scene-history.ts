import type { SceneCommand, } from "./scene-commands";
import { applySceneCommand } from "./scene-commands";
import type { SceneDocument } from "./scene-types";

export type SceneHistory = { past: SceneDocument[]; present: SceneDocument; future: SceneDocument[]; limit: number };
export function createHistory(document: SceneDocument, limit = 100): SceneHistory { return { past: [], present: document, future: [], limit }; }
export function commit(history: SceneHistory, command: SceneCommand): SceneHistory {
  const present = applySceneCommand(history.present, command);
  return { ...history, past: [...history.past, history.present].slice(-history.limit), present, future: [] };
}
export function undo(history: SceneHistory): SceneHistory { const previous = history.past.at(-1); return previous ? { ...history, past: history.past.slice(0, -1), present: previous, future: [history.present, ...history.future] } : history; }
export function redo(history: SceneHistory): SceneHistory { const next = history.future[0]; return next ? { ...history, past: [...history.past, history.present].slice(-history.limit), present: next, future: history.future.slice(1) } : history; }
