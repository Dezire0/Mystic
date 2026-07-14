import { describe, expect, it } from "vitest";
import { engineInputSchema } from "./input-schema-fallbacks";
import { normalizeDescriptor } from "./descriptor-normalizer";
import { visualizationLayerTypes } from "./descriptor-schema";

describe("Phase 2A engine product contracts", () => {
  it("supplies a bounded trusted form schema when legacy manifests are generic", () => {
    const schema = engineInputSchema("physics.simple_projectile", { type: "object" }) as Record<string, unknown>;
    expect(schema.type).toBe("object");
    expect(Object.keys(schema.properties as Record<string, unknown>)).toContain("duration_seconds");
    expect(schema.additionalProperties).toBe(false);
  });

  it("keeps every declared descriptor type renderer-safe", () => {
    const normalized = normalizeDescriptor({ version: "1", layers: visualizationLayerTypes.map((type, index) => ({ id: `layer-${index}`, type, data: type === "graph_network" ? { nodes: [], edges: [] } : { points: [] } })) });
    expect(normalized.issues).toEqual([]);
    expect(normalized.descriptor?.layers).toHaveLength(visualizationLayerTypes.length);
  });

  it("rejects an oversized graph before it reaches a renderer", () => {
    const normalized = normalizeDescriptor({ version: "1", layers: [{ id: "dense", type: "graph_network", data: { nodes: Array.from({ length: 501 }, (_, index) => ({ id: String(index) })), edges: [] } }] });
    expect(normalized.descriptor?.layers).toHaveLength(0);
    expect(normalized.issues[0]).toContain("safe display limit");
  });

  it("keeps an unknown future layer visible as an unsupported safe state", () => {
    const normalized = normalizeDescriptor({ version: "1", layers: [{ id: "future", type: "volume_mesh", data: {} }] });
    expect(normalized.descriptor?.layers).toHaveLength(1);
    expect(normalized.issues[0]).toContain("unsupported layer type");
  });
});
