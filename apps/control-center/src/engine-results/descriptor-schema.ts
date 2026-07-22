import { z } from "zod";

const finite = z.number().finite();
const safeRecord = z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null(), z.array(z.unknown()), z.record(z.string(), z.unknown())]));
export const visualizationLayerTypes = ["point", "point_set", "line", "polyline", "trajectory", "vector", "vector_field", "scalar_label", "object_state", "heatmap_points", "graph_network", "time_series_link"] as const;
export const visualizationLayerSchema = z.object({
  id: z.string().min(1).max(160), type: z.string().min(1).max(80), label: z.string().max(240).optional(), visible: z.boolean().optional(),
  data: z.record(z.string(), z.unknown()), style: safeRecord.optional(), units: safeRecord.optional(), metadata_safe: safeRecord.optional(),
}).strict();
export const visualizationDescriptorSchema = z.object({ version: z.string().max(40), layers: z.array(visualizationLayerSchema).max(64) }).strict();
export const engineManifestSchema = z.object({ engine_id: z.string().min(1), display_name: z.string().min(1), version: z.string().min(1), domain: z.string().min(1), capabilities: z.array(z.string()).max(64), manifest: z.record(z.string(), z.unknown()), enabled: z.boolean(), deprecated: z.boolean(), availability: z.string() }).passthrough();
export const engineJobSchema = z.object({ job_id: z.string().min(1), status: z.string(), engine_id: z.string(), session_id: z.string().optional(), experiment_id: z.string().optional(), scene_id: z.string().optional(), run_id: z.string().optional(), cancellation_requested: z.boolean().optional(), safe_error: z.string().optional() }).passthrough();
export const engineRunSchema = z.object({ run_id: z.string().min(1), job_id: z.string().optional(), engine_id: z.string(), engine_version: z.string().optional(), status: z.string(), session_id: z.string().optional(), experiment_id: z.string().optional(), scene_id: z.string().optional(), created_at: z.string().optional(), completed_at: z.string().optional(), summary: z.record(z.string(), z.unknown()).optional(), values: z.record(z.string(), z.unknown()).optional(), warnings: z.array(z.string()).optional(), visualization: visualizationDescriptorSchema.optional(), reproducibility: z.record(z.string(), z.unknown()).optional() }).passthrough();
export const engineArtifactSchema = z.object({ artifact_id: z.string(), artifact_type: z.string(), mime_type: z.string(), byte_size: z.number().nonnegative(), checksum: z.string(), display_name: z.string(), metadata_safe: z.record(z.string(), z.unknown()) }).passthrough();
export type EngineManifest = z.infer<typeof engineManifestSchema>;
export type EngineJob = z.infer<typeof engineJobSchema>;
export type EngineRun = z.infer<typeof engineRunSchema>;
export type VisualizationDescriptor = z.infer<typeof visualizationDescriptorSchema>;
export type VisualizationLayer = z.infer<typeof visualizationLayerSchema>;
export type EngineArtifact = z.infer<typeof engineArtifactSchema>;
export const trustedJsonSchema = z.object({ type: z.enum(["object", "array", "number", "integer", "string", "boolean"]).optional(), title: z.string().max(160).optional(), description: z.string().max(1000).optional(), default: z.unknown().optional(), enum: z.array(z.union([z.string(), z.number(), z.boolean()])).max(64).optional(), minimum: finite.optional(), maximum: finite.optional(), minItems: z.number().int().min(0).max(128).optional(), maxItems: z.number().int().min(0).max(128).optional(), minLength: z.number().int().min(0).max(10000).optional(), maxLength: z.number().int().min(0).max(10000).optional(), required: z.array(z.string()).max(64).optional(), properties: z.record(z.string(), z.unknown()).optional(), items: z.unknown().optional(), additionalProperties: z.boolean().optional() }).passthrough();
