import { visualizationDescriptorSchema, visualizationLayerTypes, type VisualizationDescriptor, type VisualizationLayer } from "./descriptor-schema";

const LIMITS = { bytes: 262_144, layers: 64, points: 10_000, vectors: 4_000, nodes: 500, edges: 1_000 };
export function normalizeDescriptor(value: unknown): { descriptor?: VisualizationDescriptor; issues: string[] } {
  const parsed = visualizationDescriptorSchema.safeParse(value); if (!parsed.success) return { issues: ["The visualization descriptor is malformed."] };
  if (new TextEncoder().encode(JSON.stringify(parsed.data)).byteLength > LIMITS.bytes) return { issues: ["The visualization descriptor exceeds its safe display limit."] };
  const layers: VisualizationLayer[] = []; const issues: string[] = [];
  for (const layer of parsed.data.layers.slice(0, LIMITS.layers)) { const data = layer.data as Record<string, unknown>; const count = Array.isArray(data.points) ? data.points.length : Array.isArray(data.vectors) ? data.vectors.length : Array.isArray(data.nodes) ? data.nodes.length : 0; const maximum = layer.type === "vector_field" ? LIMITS.vectors : layer.type === "graph_network" ? LIMITS.nodes : LIMITS.points; if (count > maximum) { issues.push(`${layer.label} exceeds its safe display limit.`); continue; } if (layer.type === "graph_network" && Array.isArray(data.edges) && data.edges.length > LIMITS.edges) { issues.push(`${layer.label} has too many graph edges.`); continue; } if (!visualizationLayerTypes.includes(layer.type as typeof visualizationLayerTypes[number])) issues.push(`${layer.label ?? layer.id} uses unsupported layer type ${layer.type}.`); layers.push(layer); }
  return { descriptor: { ...parsed.data, layers: layers.map((layer) => ({ ...layer, label: layer.label ?? "Result layer", visible: layer.visible ?? true, style: layer.style ?? {}, units: layer.units ?? {}, metadata_safe: layer.metadata_safe ?? {} })) }, issues };
}
