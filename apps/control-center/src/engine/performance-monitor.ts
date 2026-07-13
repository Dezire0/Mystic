export function sceneBudget(objects: number) {
  return { warning: objects > 100, severity: objects > 500 ? "high" : objects > 100 ? "medium" : "none", message: objects > 100 ? "Scene exceeds the Phase 1 100-primitive interaction target." : "Within Phase 1 primitive target." } as const;
}
