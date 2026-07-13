import { create } from "zustand";
import { commit, createHistory, redo as redoHistory, undo as undoHistory, type SceneHistory } from "./scene-history";
import type { SceneCommand } from "./scene-commands";
import type { SceneDocument, SyncStatus } from "./scene-types";

type EditorState = {
  history?: SceneHistory;
  selectedId?: string;
  hoveredId?: string;
  transformMode: "translate" | "rotate" | "scale";
  transformSpace: "local" | "world";
  syncStatus: SyncStatus;
  conflict?: { remote: SceneDocument; message: string };
  performanceDebug: boolean;
  resultLayerVisibility: Record<string, boolean>;
  load: (document: SceneDocument) => void;
  apply: (command: SceneCommand) => void;
  undo: () => void;
  redo: () => void;
  select: (id?: string) => void;
  hover: (id?: string) => void;
  setSyncStatus: (status: SyncStatus) => void;
  setConflict: (remote: SceneDocument, message: string) => void;
  setTransformMode: (mode: EditorState["transformMode"]) => void;
  togglePerformanceDebug: () => void;
  toggleResultLayer: (name: string) => void;
};

export const useEditorStore = create<EditorState>((set) => ({
  transformMode: "translate",
  transformSpace: "world",
  syncStatus: "loading",
  performanceDebug: false,
  resultLayerVisibility: { trajectory: true, vectors: true, markers: true, evidence: true },
  load: (document) => set({ history: createHistory(document), syncStatus: "clean", conflict: undefined }),
  apply: (command) => set((state) => state.history ? { history: commit(state.history, command), syncStatus: "dirty" } : state),
  undo: () => set((state) => state.history ? { history: undoHistory(state.history), syncStatus: "dirty" } : state),
  redo: () => set((state) => state.history ? { history: redoHistory(state.history), syncStatus: "dirty" } : state),
  select: (selectedId) => set({ selectedId }),
  hover: (hoveredId) => set({ hoveredId }),
  setSyncStatus: (syncStatus) => set({ syncStatus }),
  setConflict: (remote, message) => set({ syncStatus: "conflict", conflict: { remote, message } }),
  setTransformMode: (transformMode) => set({ transformMode }),
  togglePerformanceDebug: () => set((state) => ({ performanceDebug: !state.performanceDebug })),
  toggleResultLayer: (name) => set((state) => ({ resultLayerVisibility: { ...state.resultLayerVisibility, [name]: !state.resultLayerVisibility[name] } })),
}));
