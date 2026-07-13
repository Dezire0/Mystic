import type { SceneDocument } from "./scene-types";

export function hasRemoteConflict(local: SceneDocument, remote: SceneDocument): boolean {
  return local.revision !== remote.revision && local.updatedAt !== remote.updatedAt;
}

export function revisionPollingInterval(visible: boolean): number | false {
  return visible ? 15_000 : false;
}
